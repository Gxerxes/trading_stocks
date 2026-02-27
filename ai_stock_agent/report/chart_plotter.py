"""
日线图绘制模块 - 统一样式输出
"""

from pathlib import Path
from typing import Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from config.settings import DAILY_DATA_DIR, REPORT_DIR

matplotlib.use("Agg")


class DailyChartPlotter:
    """日线图绘制器"""

    FIGSIZE = (14, 6)
    DPI = 150
    GRID_ALPHA = 0.25
    MA_WINDOWS = (20, 60)

    @staticmethod
    def _load_csv(csv_path: Path) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        if "trade_date" not in df.columns or "close" not in df.columns:
            raise ValueError(f"CSV缺少必要列 trade_date/close: {csv_path}")

        raw_date = df["trade_date"].astype(str).str.strip().str.replace(".0", "", regex=False)
        parsed = pd.to_datetime(raw_date, format="%Y%m%d", errors="coerce")
        missing = parsed.isna()
        if missing.any():
            parsed.loc[missing] = pd.to_datetime(raw_date.loc[missing], errors="coerce")

        df["trade_date"] = parsed
        df = df.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
        return df

    @staticmethod
    def _find_latest_csv(ts_code: str, data_dir: Path = DAILY_DATA_DIR) -> Path:
        matches = list(data_dir.glob(f"{ts_code}*.csv"))
        if not matches:
            raise FileNotFoundError(f"未找到 {ts_code} 对应CSV: {data_dir}")
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return matches[0]

    @classmethod
    def plot_from_csv(
        cls,
        csv_path: Path,
        output_path: Optional[Path] = None,
        ma_windows: Tuple[int, int] = MA_WINDOWS,
    ) -> Path:
        df = cls._load_csv(csv_path)

        ma_short, ma_long = ma_windows
        df[f"MA{ma_short}"] = df["close"].rolling(ma_short, min_periods=1).mean()
        df[f"MA{ma_long}"] = df["close"].rolling(ma_long, min_periods=1).mean()

        ts_code = csv_path.stem.split("_")[0]
        if output_path is None:
            output_dir = REPORT_DIR / "charts"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{ts_code}_daily_trend.png"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=cls.FIGSIZE)
        plt.plot(df["trade_date"], df["close"], label="Close", linewidth=1.0)
        plt.plot(df["trade_date"], df[f"MA{ma_short}"], label=f"MA{ma_short}", linewidth=1.0)
        plt.plot(df["trade_date"], df[f"MA{ma_long}"], label=f"MA{ma_long}", linewidth=1.0)
        plt.title(f"{ts_code} Daily Trend")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        plt.grid(alpha=cls.GRID_ALPHA)
        plt.tight_layout()
        plt.savefig(output_path, dpi=cls.DPI)
        plt.close()
        return output_path

    @classmethod
    def plot_from_ts_code(
        cls,
        ts_code: str,
        output_path: Optional[Path] = None,
        data_dir: Path = DAILY_DATA_DIR,
        ma_windows: Tuple[int, int] = MA_WINDOWS,
    ) -> Path:
        csv_path = cls._find_latest_csv(ts_code, data_dir)
        return cls.plot_from_csv(csv_path=csv_path, output_path=output_path, ma_windows=ma_windows)
