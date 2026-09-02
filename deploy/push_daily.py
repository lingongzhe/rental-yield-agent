# -*- coding: utf-8 -*-
"""本机每日任务：采集链家真实数据 → 生成报告 → 自动推送到 GitHub Pages。

逻辑：
  1) 在本机(国内网络)运行 main.py，抓到链家真实数据并生成报告。
  2) 若生成了真实报告（非"未获取到真实数据"提示页），复制到 docs/index.html。
  3) git 提交并 push 到远程仓库，触发 GitHub Actions / Pages 自动更新。
  4) 若本次仍是提示页（例如链家临时反爬），则不上推，避免覆盖线上真实数据。

由 push_daily.bat 或 Windows 计划任务调用。
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RUNNER = os.path.join(ROOT, "runner")
REPORT = os.path.join(RUNNER, "output", "rental-report.html")
DOCS_INDEX = os.path.join(ROOT, "docs", "index.html")
LOG = os.path.join(RUNNER, "output", "push_daily.log")

_TOKEN = os.path.normpath(os.path.join(HERE, "..", "..", "rv-crawler", "deploy", ".gh_token"))
REMOTE = "https://x-access-token:{token}@github.com/lingongzhe/rental-yield-agent.git"


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(msg) + "\n")
    print(msg)


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def main():
    log("==== 每日真实数据推送开始 ====")

    # 1) 本机抓真实数据并生成报告
    py = sys.executable
    r = run([py, "main.py"], cwd=RUNNER)
    log("main.py 退出码 = %s" % r.returncode)
    if r.stdout:
        log("STDOUT: " + r.stdout.strip()[:800])
    if r.stderr:
        log("STDERR: " + r.stderr.strip()[:800])

    # 2) 检查是否是提示页
    if not os.path.exists(REPORT):
        log("未生成报告，跳过推送。")
        return
    with open(REPORT, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    if "未获取到真实数据" in content:
        log("本次为提示页(未抓到真实数据)。线上保持上次真实内容，不推送覆盖。")
        return

    # 3) 复制到 docs
    os.makedirs(os.path.dirname(DOCS_INDEX), exist_ok=True)
    shutil.copyfile(REPORT, DOCS_INDEX)
    log("已同步真实报告到 docs/index.html")

    # 4) git commit + push
    token = ""
    if os.path.exists(_TOKEN):
        with open(_TOKEN, encoding="utf-8") as f:
            token = f.read().strip()
    git = ["git", "-C", ROOT]
    run(git + ["add", "-A"], cwd=ROOT)
    cmsg = "auto: 每日真实收租报告 " + time.strftime("%Y-%m-%d %H:%M")
    rc = run(git + ["-c", "user.name=lingongzhe",
                    "-c", "user.email=lingongzhe@users.noreply.github.com",
                    "commit", "-m", cmsg], cwd=ROOT)
    if rc.returncode != 0:
        log("无可提交变更或提交已存在：" + (rc.stderr or rc.stdout or "").strip()[:300])
    if token:
        remote = REMOTE.format(token=token)
    else:
        remote = "origin"
    pr = run(git + ["push", remote, "main:main"], cwd=ROOT)
    if pr.returncode == 0:
        log("推送成功！线上 Pages 将自动更新为真实数据。")
    else:
        log("推送失败：" + (pr.stderr or pr.stdout or "").strip()[:500])
    log("==== 推送结束 ====")


if __name__ == "__main__":
    main()