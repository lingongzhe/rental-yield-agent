# -*- coding: utf-8 -*-
"""CDP 导航到目标网站，让页面 JS 生成 anti-bot Cookie，再抓取写入 house-cli cookies.json。

原理：58/安居客 的 JS anti-bot 需要浏览器执行脚本生成 xxzlclientid 等 Cookie。
house-cli 用 httpx 直接请求拿不到这些 Cookie，所以被拦。用 Chrome 访问一次页面，
JS 自动生成完整 Cookie，CDP 抓取后 house-cli 即可复用。
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

PORT = 9224
PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                       "output", "_cdp_profile")
TARGETS = {
    "58.com": "https://sy.58.com/ershoufang/",
    "anjuke.com": "https://shenyang.anjuke.com/sale/",
    "fang.com": "https://sy.esf.fang.com/",
    "zhuge.com": "https://shenyang.zhuge.com/ershoufang/",
    "ke.com": "https://sy.ke.com/ershoufang/",
}
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "output", "cookies_export.log")


def _find_chrome():
    for c in (os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
              os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
              os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")):
        if os.path.exists(c):
            return c
    return None


def _reg_domain(host):
    h = host.lstrip(".")
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


async def _cdp(ws_url, method, params=None, mid=1):
    import websockets
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if msg.get("id") == mid:
                return msg


def main():
    lines = []
    def say(s):
        print(s)
        lines.append(s)

    say("=" * 58)
    say("  浏览器 anti-bot Cookie 自动生成")
    say("=" * 58)
    chrome = _find_chrome()
    if not chrome:
        say("[错误] 未找到 Chrome。")
        return _finish(lines, 1)

    os.makedirs(PROFILE, exist_ok=True)
    proc = subprocess.Popen(
        [chrome, "--remote-debugging-port={}".format(PORT),
         "--remote-debugging-address=127.0.0.1", "--user-data-dir={}".format(PROFILE),
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(40):
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:{}/json/version".format(PORT), timeout=2) as r:
                ws_url = json.loads(r.read().decode("utf-8"))["webSocketDebuggerUrl"]
            if ws_url:
                break
        except Exception:
            time.sleep(0.5)
    if not ws_url:
        say("[错误] Chrome 调试端口未就绪。")
        _kill(proc)
        return _finish(lines, 1)

    ok = []
    for domain, url in TARGETS.items():
        try:
            # 新开 tab 导航
            t = asyncio.run(_cdp(ws_url, "Target.createTarget",
                                 {"url": "about:blank"}, mid=1))
            tid = t["result"]["targetId"]
            turl = "ws://127.0.0.1:{}/devtools/page/{}".format(PORT, tid)
            # 等 tab 就绪
            for _ in range(20):
                try:
                    with urllib.request.urlopen(
                            "http://127.0.0.1:{}/json".format(PORT), timeout=2) as r:
                        pages = json.loads(r.read().decode("utf-8"))
                    if any(p.get("id") == tid for p in pages):
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            # 导航到目标站
            asyncio.run(_cdp(turl, "Page.navigate", {"url": url}, mid=1))
            time.sleep(6)  # 等 JS anti-bot 执行
            # 抓 Cookie
            cookies = asyncio.run(_cdp(turl, "Network.getAllCookies", {}, mid=2))
            cks = cookies.get("result", {}).get("cookies", [])
            by_domain = {}
            for c in cks:
                d = _reg_domain(c.get("domain", ""))
                if d == domain:
                    by_domain[c["name"]] = c["value"]
            if by_domain:
                auth.save_cookies(domain, by_domain)
                ok.append(domain)
                say("  ✓ {d:12s} 生成并写入 {n} 个 Cookie".format(d=domain, n=len(by_domain)))
            else:
                say("  · {d:12s} 未生成 Cookie".format(d=domain))
            asyncio.run(_cdp(ws_url, "Target.closeTarget", {"targetId": tid}, mid=3))
        except Exception as e:  # noqa: BLE001
            say("  ✗ {d:12s} 失败：{e}".format(d=domain, e=str(e)[:100]))

    say("-" * 58)
    if ok:
        say("  已写入：{}".format(auth.COOKIE_FILE))
        say("  成功平台：{}".format(", ".join(ok)))
    else:
        say("  未生成任何 Cookie。")

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
