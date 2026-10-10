#!/usr/bin/env python3
"""端到端冒烟测试：启动服务 → 探测 /api/status 与 /api/plugins → 关停。

用途：
  - 本地快速验证（Windows / Linux / macOS 均可）
  - CI 矩阵中的跨平台回归门禁

用法：
  python scripts/smoke_serve.py [--port 8083] [--timeout 60]
退出码：0 成功；非 0 失败（CI 可直接使用）
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request


def main() -> int:
    # 控制台/管道可能是 GBK：打印子进程日志时降级替换，避免 UnicodeEncodeError 把测试打断
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8083)
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 强制 UTF-8，避免 Windows GBK 管道解码问题
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    base = "http://127.0.0.1:%d" % args.port
    proc = None
    ok = False
    try:
        # 子进程日志写文件而非管道：插件启动日志量很大，管道不读取会把子进程写阻塞导致假死
        log_path = os.path.join(tempfile.gettempdir(), "astrum-smoke-%d.log" % args.port)
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            [sys.executable, "-u", "main.py", "serve", "--port", str(args.port)],
            cwd=root,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(base + "/api/status", timeout=3) as r:
                    status = json.loads(r.read().decode("utf-8"))
                with urllib.request.urlopen(base + "/api/plugins", timeout=5) as r:
                    plugins = json.loads(r.read().decode("utf-8"))
                print("[smoke] /api/status = %s" % status)
                print("[smoke] 插件数 = %d" % len(plugins))
                assert status.get("status") == "running", status
                assert status.get("plugins_loaded") is True, status
                assert len(plugins) > 0, "没有任何插件被加载"
                ok = True
                break
            except Exception:
                time.sleep(1.0)
        if not ok:
            print("[smoke] 失败：服务未在 %.0fs 内就绪" % args.timeout)
    finally:
        if proc is not None:
            try:
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGINT)
            except Exception:
                pass
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
            try:
                log_file.close()
            except Exception:
                pass
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            except Exception:
                lines = []
            # 被强制终止时服务来不及清理 .pid，这里兜底清掉，避免下次启动被误判为"已在运行"
            try:
                pid_path = os.path.join(root, ".pid")
                if os.path.exists(pid_path):
                    os.remove(pid_path)
            except Exception:
                pass
            print("[smoke] --- 服务日志末尾 40 行（完整日志：%s）---" % log_path)
            print("\n".join(lines[-40:]))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
