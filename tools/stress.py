"""壓力測試：對測試目標連續觸發 N 次，記錄常駐程式的記憶體(RSS)、執行緒數與 handle 數變化。

用法：python tools/stress.py [--target tk|chrome|edge|word|pdfx] [--count 50] [--warmup 5]
驗收：N 次皆成功、USS 成長 < 5MB、執行緒與 handle 數不持續增加。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compat as c  # noqa: E402


def snapshot(app: subprocess.Popen) -> dict:
    procs = [psutil.Process(pid) for pid in c.tree_pids(app)]
    # RSS 含共用 DLL 頁面（Qt 約 70MB），成長判斷以 USS（行程獨占記憶體）為準
    return {
        "uss_mb": sum(p.memory_full_info().uss for p in procs) / 1e6,
        "rss_mb": sum(p.memory_info().rss for p in procs) / 1e6,
        "threads": sum(p.num_threads() for p in procs),
        "handles": sum(p.num_handles() for p in procs),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="tk")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--warmup", type=int, default=5, help="不計入成長的暖機次數")
    args = ap.parse_args()

    workdir = Path(c.tempfile.mkdtemp(prefix="compat_docs_"))
    docs = c.make_docs(workdir)
    original = c.ps("Get-Clipboard -Raw")
    env = {**os.environ, "PYTHONUTF8": "1", "HOTKEYDICT_LOG_WORDS": "1"}
    app = c.start_app(env)
    time.sleep(3)
    try:
        pids = c.tree_pids(app)
        marks: dict[str, dict] = {}

        def on_iter(i: int) -> None:
            if i == args.warmup - 1:            # 暖機（首次繪製、快取）結束後才取基準值
                marks["before"] = snapshot(app)

        res = c.run_one(args.target, docs, workdir, None, args.warmup + args.count, pids, on_iter)
        after = snapshot(app)
        before = marks["before"]
    finally:
        c.kill_tree(app)
        if original:
            subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
                           input=original, text=True, encoding="utf-8")
    print(f"target={args.target} pass={res.get('pass')} latency={res.get('latency_ms')}")
    for key in ("uss_mb", "rss_mb", "threads", "handles"):
        print(f"{key:8s} before={before[key]:8.1f} after={after[key]:8.1f} delta={after[key] - before[key]:+.1f}")
    bad = [f"#{n}: {i}" for n, i in enumerate(res.get("iters", [])) if not i.startswith("ok")]
    if bad:
        print("non-ok iterations:", bad[:10])


if __name__ == "__main__":
    main()
