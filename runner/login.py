# -*- coding: utf-8 -*-
"""登录链家并保存登录态，供无头批量采集使用。

用法： python login.py
流程：弹出带界面的浏览器 → 打开贝壳/链家 → 你手动完成登录（手机号验证码等）
      → 回到本窗口按回车 → 登录态 Cookie 保存到 runner/.lianjia_cookies.json。
说明：登录态仅保存在本机，不会上传；每日任务会携带它翻页抓取更多真实数据。
      建议使用【不常用的手机号】登录，以降低账号风控影响。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright  # noqa: E402
import headless  # noqa: E402

COOKIES_FILE = headless.COOKIES_FILE


def main():
    print("=" * 56)
    print("  链家 / 贝壳 登录态采集 · 登录一次")
    print("  弹出浏览器后，请自行完成登录（推荐手机号验证码）。")
    print("=" * 56)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1366, "height": 850},
                                  locale="zh-CN")
        page = ctx.new_page()
        page.goto("https://sy.lianjia.com/ershoufang/",
                  wait_until="domcontentloaded", timeout=30000)
        input("\n>>> 请在浏览器里登录完成后，回到这里按回车保存 ... ")
        cookies = [c for c in ctx.cookies()
                   if any(c["domain"].endswith(d)
                          for d in ("lianjia.com", ".ke.com", ".beike.com"))]
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(__import__("json").dumps(cookies, ensure_ascii=False, indent=1))
        print("\n已保存 {n} 条登录态 Cookie → {path}".format(n=len(cookies), path=COOKIES_FILE))
        browser.close()
    print("完成！之后每日任务将优先走登录态批量采集（量大）。")
    print("删除 {file} 即可恢复为免费的首页首屏采集。".format(file=COOKIES_FILE))


if __name__ == "__main__":
    main()