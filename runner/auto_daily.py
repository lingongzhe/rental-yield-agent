# -*- coding: utf-8 -*-
"""计划任务入口：直接运行主程序，并把输出写入日志。
用法： python auto_daily.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
OUT_DIR = os.path.join(HERE, "output")
os.makedirs(OUT_DIR, exist_ok=True)
LOG = os.path.join(OUT_DIR, "daily.log")


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(msg) + "\n")


def main():
    log("==== 每日运行开始 ====")
    try:
        r = subprocess.run([PY, "main.py"], cwd=HERE,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.stdout:
            log("STDOUT:\n" + r.stdout.strip())
        if r.stderr:
            log("STDERR:\n" + r.stderr.strip())
        log("main.py 退出码 = %s" % r.returncode)
    except Exception as e:
        log("运行异常: %s" % e)
    log("==== 每日运行结束 ====")


if __name__ == "__main__":
    main()