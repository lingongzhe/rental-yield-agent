# -*- coding: utf-8 -*-
"""用 Chrome DevTools Protocol 提取浏览器登录态 → house-cli 的 cookies.json。

为什么不用 browser_cookie3：Chrome 127+ 对登录态 Cookie 用 App-Bound Encryption，
browser_cookie3 即使管理员权限也解不了（只能解普通 Cookie）。CDP 让 Chrome 自己
解密并上报，能拿到完整的 HttpOnly + App-Bound 登录态，且无需管理员权限。

流程：启动 Chrome(默认 profile, remote-debugging) → CDP Network.getAllCookies →
按注册域分组写入 ~/.config/house-cli/cookies.json → 关闭 Chrome。
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HOUSE_CLI_SRC = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "house-cli", "src"))
if os.path.isdir(HOUSE_CLI_SRC):
    sys.path.insert(0, HOUSE_CLI_SRC)
    from house_cli.client import auth  # noqa: E402
else:
    print("[错误] 未找到 house-cli 源码目录：{}".format(HOUSE_CLI_SRC))
    sys.exit(1)

PORT = 9222
# 目标注册域（house-cli adapter 用的 key）
TARGET_DOMAINS = ["ke.com", "lianjia.com", "anjuke.com", "58.com",
                  "fang.com", "zhuge.com", "ziroom.com"]

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "output", "cookies_export.log")


def _find_chrome():
    cands = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def _reg_domain(host):
    """CDP 的 host(如 .anjuke.com / passport.58.com) → 注册域(anjuke.com / 58.com)。"""
    h = host.lstrip(".")
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


async def _get_cookies(ws_url):
    import websockets
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        await ws.recv()
        await ws.send(json.dumps({"id": 2, "method": "Network.getAllCookies"}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 2:
                return msg["result"]["cookies"]


def main():
    lines = []
    def say(s):
        print(s)
        lines.append(s)

    say("=" * 58)
    say("  Chrome CDP 登录态提取（无需管理员）")
    say("=" * 58)

    chrome = _find_chrome()
    if not chrome:
        say("[错误] 未找到 Chrome，请确认已安装。")
        return _finish(lines, 1)

    # 1) 启动 Chrome（默认 profile，带调试端口）
    say("  启动 Chrome(调试端口 {}) ...".format(PORT))
    proc = subprocess.Popen(
        [chrome, "--remote-debugging-port={}".format(PORT),
         "--remote-debugging-address=127.0.0.1", "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2) 等 CDP 就绪
    ws_url = None
    for _ in range(40):
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:{}/json/version".format(PORT), timeout=2) as r:
                v = json.loads(r.read().decode("utf-8"))
            ws_url = v.get("webSocketDebuggerUrl")
            if ws_url:
                break
        except Exception:
            time.sleep(0.5)
    if not ws_url:
        say("[错误] Chrome 调试端口未就绪。")
        _kill(proc)
        return _finish(lines, 1)

    # 3) 取全部 Cookie
    try:
        cookies = asyncio.run(_get_cookies(ws_url))
    except Exception as e:  # noqa: BLE001
        say("[错误] CDP 获取 Cookie 失败：{}".format(str(e)[:120]))
        _kill(proc)
        return _finish(lines, 1)

    # 4) 按注册域分组
    by_domain = {}
    for c in cookies:
        d = _reg_domain(c.get("domain", ""))
        if d in TARGET_DOMAINS:
            by_domain.setdefault(d, {})[c["name"]] = c["value"]

    # 5) 写入 house-cli cookies.json
    ok = []
    for d in TARGET_DOMAINS:
        ck = by_domain.get(d)
        if ck:
            auth.save_cookies(d, ck)
            ok.append(d)
            say("  ✓ {d:12s} 提取 {n} 个 Cookie".format(d=d, n=len(ck)))
        else:
            say("  · {d:12s} 无 Cookie（未登录或未访问）".format(d=d))

    say("-" * 58)
    if ok:
        say("  已写入：{}".format(auth.COOKIE_FILE))
        say("  成功平台：{}".format(", ".join(ok)))
        say("  有效期约 7 天，过期后重跑本脚本即可。")
    else:
        say("  未提取到任何目标平台 Cookie。")

    _kill(proc)
    return _finish(lines, 0)


def _kill(proc):
    try:
        proc.terminate()
        time.sleep(1)
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                       capture_output=True, text=True)
    except Exception:
        pass


def _finish(lines, code):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        pass
    return code


if __name__ == "__main__":
    sys.exit(main())
