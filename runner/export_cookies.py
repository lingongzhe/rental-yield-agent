# -*- coding: utf-8 -*-
"""一键提取浏览器登录态 → house-cli 的 cookies.json。

背景：house-cli 的贝壳/安居客/58/诸葛等 adapter 需要浏览器 Cookie；
Windows 上 browser_cookie3 读取 Chrome/Edge 加密 Cookie 需要管理员权限，
普通运行时提取失败（RequiresAdminError）。本脚本以管理员身份运行一次，
把已登录平台的 Cookie 写入 ~/.config/house-cli/cookies.json（7 天有效），
之后普通运行 main.py --refresh 即可自动使用多平台数据。

用法：右键本脚本所在目录的 export_cookies.bat → “以管理员身份运行”。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 提取结果同时写一份日志，便于提权运行后查看
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "output", "cookies_export.log")

# 复用 house-cli 的 auth 模块（提取 + 自动保存到 cookies.json）
HOUSE_CLI_SRC = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "house-cli", "src"))
if os.path.isdir(HOUSE_CLI_SRC):
    sys.path.insert(0, HOUSE_CLI_SRC)
    from house_cli.client import auth  # noqa: E402
else:
    print("[错误] 未找到 house-cli 源码目录：{}".format(HOUSE_CLI_SRC))
    print("       请先 git clone https://github.com/lingongzhe/house-cli.git")
    sys.exit(1)

# 目标域名：贝壳/链家、安居客、58同城、房天下、诸葛找房
DOMAINS = ["ke.com", "lianjia.com", "anjuke.com", "58.com", "fang.com", "zhuge.com"]


def _is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def main():
    lines = []
    def say(s):
        print(s)
        lines.append(s)

    say("=" * 58)
    say("  house-cli 浏览器登录态一键提取")
    say("=" * 58)
    if not _is_admin():
        say("\n[提示] 当前不是管理员权限，提取 Chrome/Edge Cookie 可能失败。")
        say("        建议：关闭本窗口，右键 export_cookies.bat → 以管理员身份运行。\n")

    ok_domains = []
    for domain in DOMAINS:
        try:
            cookies = auth.load_or_extract_cookies(domain)
            n = len(cookies)
            if n:
                ok_domains.append(domain)
                say("  ✓ {d:12s} 提取 {n} 个 Cookie".format(d=domain, n=n))
            else:
                say("  · {d:12s} 未找到登录态（可能未登录或浏览器不支持）".format(d=domain))
        except Exception as e:  # noqa: BLE001
            say("  ✗ {d:12s} 提取失败：{e}".format(d=domain, e=str(e)[:80]))

    say("-" * 58)
    if ok_domains:
        say("  已写入：{}".format(auth.COOKIE_FILE))
        say("  成功平台：{}".format(", ".join(ok_domains)))
        say("  有效期约 7 天，过期后重新运行本脚本即可。")
        say("  现在可正常执行： python runner\\main.py --refresh")
    else:
        say("  未提取到任何登录态。请确认：")
        say("  1) 已用 Chrome/Edge 登录对应网站；")
        say("  2) 以管理员身份运行本脚本。")

    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
