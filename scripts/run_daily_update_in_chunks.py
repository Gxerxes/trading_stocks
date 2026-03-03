"""
按分组循环调用 daily_update_pipeline.py 下载数据。

用途：
- 大股票池分批下载，降低单次任务时长和失败影响范围
- 默认每组 50 只

示例：
python scripts/run_daily_update_in_chunks.py
python scripts/run_daily_update_in_chunks.py --chunk-size 50 --stock-pool ai_stock_agent/data/stock_pool.json
python scripts/run_daily_update_in_chunks.py --chunk-size 50 --skip-minute
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DATA = PROJECT_ROOT / "ai_stock_agent" / "data"
DEFAULT_STOCK_POOL = APP_DATA / "stock_pool.json"
CHUNK_POOL_DIR = APP_DATA / "pipeline_state" / "chunk_pools"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="按分组循环执行 daily_update_pipeline")
    p.add_argument("--stock-pool", type=str, default=str(DEFAULT_STOCK_POOL), help="股票池 JSON 文件")
    p.add_argument("--chunk-size", type=int, default=50, help="每组股票数量，默认 50")
    p.add_argument("--run-date", type=str, default=None, help="运行日期 YYYYMMDD")
    p.add_argument("--minute-frequency", type=str, default="5", choices=["5", "15", "30", "60"], help="分钟周期")
    p.add_argument("--skip-minute", action="store_true", help="跳过分钟线")
    p.add_argument("--skip-lake", action="store_true", help="跳过写入 lake")
    p.add_argument("--initial-start-date", type=str, default="19900101", help="首次下载起始日期")
    p.add_argument("--sleep-seconds", type=float, default=0.08, help="单只股票请求间隔秒数")
    p.add_argument("--start-chunk", type=int, default=1, help="从第几组开始（1-based）")
    p.add_argument("--end-chunk", type=int, default=None, help="到第几组结束（1-based，默认最后一组）")
    p.add_argument("--stop-on-error", action="store_true", help="遇到组失败时立即停止")
    return p.parse_args()


def load_pool(path: Path) -> tuple[list[str], dict[str, str], str]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    stocks = [str(x).strip().upper() for x in obj.get("stocks", []) if str(x).strip()]
    name_map: dict[str, str] = {}
    for item in obj.get("stocks_detail", []):
        if isinstance(item, dict):
            code = str(item.get("ts_code", "")).strip().upper()
            name = str(item.get("name", "")).strip()
            if code:
                name_map[code] = name
    desc = str(obj.get("description", "")).strip()
    return stocks, name_map, desc


def chunked(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def write_chunk_pool(
    stocks: list[str],
    name_map: dict[str, str],
    desc: str,
    source_stem: str,
    idx: int,
    total: int,
) -> Path:
    CHUNK_POOL_DIR.mkdir(parents=True, exist_ok=True)
    out = CHUNK_POOL_DIR / f"{source_stem}_chunk_{idx:03d}_of_{total:03d}.json"
    obj = {
        "stocks": stocks,
        "description": f"{desc} | chunk {idx}/{total}".strip(),
        "stocks_detail": [{"ts_code": s, "name": name_map.get(s, "")} for s in stocks],
    }
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_one_chunk(chunk_pool_path: Path, args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "daily_update_pipeline.py"),
        "--stock-pool",
        str(chunk_pool_path),
        "--minute-frequency",
        args.minute_frequency,
        "--initial-start-date",
        args.initial_start_date,
        "--sleep-seconds",
        str(args.sleep_seconds),
    ]
    if args.run_date:
        cmd += ["--run-date", args.run_date]
    if args.skip_minute:
        cmd.append("--skip-minute")
    if args.skip_lake:
        cmd.append("--skip-lake")
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return int(res.returncode)


def main() -> None:
    args = parse_args()
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size 必须 > 0")

    pool_path = Path(args.stock_pool)
    stocks, name_map, desc = load_pool(pool_path)
    if not stocks:
        raise ValueError(f"股票池为空: {pool_path}")

    groups = chunked(stocks, args.chunk_size)
    total = len(groups)
    start = max(1, args.start_chunk)
    end = args.end_chunk if args.end_chunk is not None else total
    end = min(end, total)
    if start > end:
        raise ValueError(f"无效区间: start={start}, end={end}, total={total}")

    source_stem = pool_path.stem
    failed: list[int] = []
    succeeded = 0

    print(f"total_stocks={len(stocks)} chunk_size={args.chunk_size} total_chunks={total}")
    print(f"run_chunks={start}..{end}")

    for idx in range(start, end + 1):
        chunk_stocks = groups[idx - 1]
        chunk_pool = write_chunk_pool(chunk_stocks, name_map, desc, source_stem, idx, total)
        print(f"[chunk {idx}/{total}] stocks={len(chunk_stocks)} pool={chunk_pool}")
        code = run_one_chunk(chunk_pool, args)
        if code == 0:
            succeeded += 1
            print(f"[chunk {idx}/{total}] ok")
        else:
            failed.append(idx)
            print(f"[chunk {idx}/{total}] failed exit_code={code}")
            if args.stop_on_error:
                break

    print(
        "summary "
        f"chunks_total={end-start+1} chunks_ok={succeeded} "
        f"chunks_failed={len(failed)} failed_list={failed}"
    )


if __name__ == "__main__":
    main()
