"""
Tushare API 数据下载模块
"""

import logging
import pandas as pd
import tushare as ts
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from config.settings import (
    TUSHARE_TOKEN,
    RETRY_ATTEMPTS,
    DAILY_DATA_DIR,
    DATA_DIR,
    DAILY_HISTORY_DIR,
)

logger = logging.getLogger(__name__)

STOCK_DAILY_COLUMNS = [
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
]

STOCK_BASIC_COLUMNS = [
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "fullname",
    "enname",
    "cnspell",
    "market",
    "exchange",
    "curr_type",
    "list_status",
    "list_date",
    "delist_date",
    "is_hs",
    "act_name",
    "act_ent_type",
]

DAILY_BASIC_COLUMNS = [
    "ts_code",
    "trade_date",
    "close",
    "turnover_rate",
    "turnover_rate_f",
    "volume_ratio",
    "pe",
    "pe_ttm",
    "pb",
    "ps",
    "ps_ttm",
    "dv_ratio",
    "dv_ttm",
    "total_share",
    "float_share",
    "free_share",
    "total_mv",
    "circ_mv",
]


class TushareDownloader:
    """Tushare数据下载器"""
    
    def __init__(self):
        """初始化 Tushare API"""
        try:
            ts.set_token(TUSHARE_TOKEN)
            self.pro = ts.pro_api()
            logger.info("Tushare API 初始化成功")
        except Exception as e:
            logger.error(f"Tushare API 初始化失败: {e}")
            raise
    
    def get_daily_data(
        self, 
        ts_code: str, 
        days: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取股票日线数据
        
        Args:
            ts_code: 股票代码，如 '000001.SZ'
            days: 获取过去多少天的数据，None 表示下载全历史
            
        Returns:
            DataFrame，包含:
            ts_code, trade_date, close, open, high, low,
            pre_close, change, pct_chg, vol, amount
        """
        try:
            end_date = datetime.now()
            end_date_str = end_date.strftime("%Y%m%d")
            existing_df: Optional[pd.DataFrame] = None

            # days=None 时默认走增量更新：读取本地已下载CSV并只拉取新数据
            if days is None:
                existing_file = self._find_latest_csv_file(ts_code, DAILY_DATA_DIR)
                if existing_file is not None:
                    existing_df = self._load_csv_file(existing_file)
                    if existing_df is not None and not existing_df.empty:
                        if self._is_cache_corrupted(existing_df):
                            logger.warning(f"{ts_code} 本地CSV日期异常，自动全量重下载")
                            existing_df = None
                            start_date_str = "19900101"
                        else:
                            last_trade_date = existing_df["trade_date"].max()
                            next_trade_date = last_trade_date + timedelta(days=1)
                            if next_trade_date > end_date:
                                logger.info(f"{ts_code} 本地数据已是最新，无需下载")
                                return existing_df
                            start_date_str = next_trade_date.strftime("%Y%m%d")
                            logger.info(
                                f"{ts_code} 增量下载区间: {start_date_str} ~ {end_date_str}"
                            )
                    else:
                        existing_df = None
                        start_date_str = "19900101"
                else:
                    start_date_str = "19900101"
            else:
                start_date = end_date - timedelta(days=days)
                start_date_str = start_date.strftime("%Y%m%d")

            df = None
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    df = self.pro.daily(
                        ts_code=ts_code,
                        start_date=start_date_str,
                        end_date=end_date_str,
                        fields="ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
                    )
                    if df is not None and len(df) > 0:
                        break
                except Exception as e:
                    logger.warning(f"第 {attempt+1} 次尝试获取 {ts_code} 数据失败: {e}")
                    if attempt == RETRY_ATTEMPTS - 1:
                        raise

            if df is None or len(df) == 0:
                if existing_df is not None and not existing_df.empty:
                    logger.info(f"{ts_code} 无新增数据，使用本地CSV")
                    return existing_df
                logger.warning(f"未能获取 {ts_code} 有效数据")
                return None

            new_df = self._normalize_daily_df(df)
            if existing_df is not None and not existing_df.empty:
                merged_df = pd.concat([existing_df, new_df], ignore_index=True)
                merged_df = merged_df.drop_duplicates(
                    subset=["trade_date"], keep="last"
                ).sort_values("trade_date").reset_index(drop=True)
                logger.info(
                    f"{ts_code} 增量更新完成，新增 {len(new_df)} 条，总计 {len(merged_df)} 条"
                )
                return merged_df

            logger.info(f"成功获取 {ts_code} 的 {len(new_df)} 条数据")
            return new_df
            
        except Exception as e:
            logger.error(f"获取 {ts_code} 数据异常: {e}")
            return None

    @staticmethod
    def _normalize_daily_df(df: pd.DataFrame) -> pd.DataFrame:
        """标准化日线数据格式和字段顺序"""
        normalized = df.copy()
        normalized["trade_date"] = TushareDownloader._parse_trade_date_series(
            normalized["trade_date"]
        )
        normalized = normalized.dropna(subset=["trade_date"])
        normalized = normalized.sort_values("trade_date").reset_index(drop=True)

        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "vol",
            "amount",
        ]
        for col in numeric_cols:
            if col in normalized.columns:
                normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

        available_columns = [col for col in STOCK_DAILY_COLUMNS if col in normalized.columns]
        return normalized[available_columns]

    @staticmethod
    def _parse_trade_date_series(series: pd.Series) -> pd.Series:
        """
        兼容解析交易日：
        - 优先解析 YYYYMMDD（防止被当成纳秒时间戳）
        - 其次回退通用日期解析（如 YYYY-MM-DD）
        """
        s = series.astype(str).str.strip().str.replace(".0", "", regex=False)
        parsed = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
        mask = parsed.isna()
        if mask.any():
            parsed.loc[mask] = pd.to_datetime(s.loc[mask], errors="coerce")
        return parsed

    @staticmethod
    def _is_cache_corrupted(df: pd.DataFrame) -> bool:
        """
        判断本地缓存日期是否异常。
        A股交易数据不应早于 1990 年，出现则视为缓存损坏。
        """
        if "trade_date" not in df.columns or df.empty:
            return True
        min_date = df["trade_date"].min()
        if pd.isna(min_date):
            return True
        return min_date.year < 1990

    @staticmethod
    def _find_latest_csv_file(ts_code: str, output_dir: Path) -> Optional[Path]:
        """查找某股票在目录中的最新CSV文件（按文件名结束日期）"""
        candidates = list(output_dir.glob(f"{ts_code}_*.csv"))
        if not candidates:
            return None

        def end_date_key(path: Path):
            parts = path.stem.split("_")
            if len(parts) >= 3 and parts[-1].isdigit():
                return parts[-1]
            return "00000000"

        candidates.sort(key=end_date_key, reverse=True)
        return candidates[0]

    def _load_csv_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """加载本地CSV并转换为标准DataFrame"""
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                return None

            if "trade_date" not in df.columns:
                logger.warning(f"{file_path} 缺少 trade_date 字段，忽略本地缓存")
                return None

            normalized = self._normalize_daily_df(df)
            if normalized.empty:
                return None
            return normalized
        except Exception as e:
            logger.warning(f"读取本地CSV失败，忽略缓存: {file_path}, 错误: {e}")
            return None
    
    def get_multiple_stocks(
        self,
        ts_codes: List[str],
        days: Optional[int] = None
    ) -> dict:
        """
        批量获取多个股票的日线数据
        
        Args:
            ts_codes: 股票代码列表
            days: 获取过去多少天的数据，None 表示下载全历史
            
        Returns:
            字典，key为ts_code，value为DataFrame
        """
        result = {}
        
        for ts_code in ts_codes:
            logger.info(f"正在下载 {ts_code} 数据...")
            df = self.get_daily_data(ts_code, days)
            if df is not None:
                result[ts_code] = df
            else:
                logger.warning(f"跳过 {ts_code}，未获取到数据")
        
        logger.info(f"完成 {len(result)} 个股票的数据下载")
        return result

    @staticmethod
    def save_to_csv_batch(
        data_dict: dict,
        output_dir: Path = DAILY_DATA_DIR
    ) -> List[Path]:
        """
        将每只股票的日线数据保存为独立CSV文件

        Args:
            data_dict: 股票数据字典，key为ts_code，value为DataFrame
            output_dir: 输出目录

        Returns:
            保存成功的文件路径列表
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files: List[Path] = []

        for ts_code, df in data_dict.items():
            if df is None or df.empty:
                logger.warning(f"{ts_code} 数据为空，跳过CSV保存")
                continue

            df_to_save = df.copy()
            start_date = "unknown"
            end_date = "unknown"

            if "trade_date" in df_to_save.columns:
                trade_dates = pd.to_datetime(df_to_save["trade_date"], errors="coerce").dropna()
                if not trade_dates.empty:
                    start_date = trade_dates.min().strftime("%Y%m%d")
                    end_date = trade_dates.max().strftime("%Y%m%d")
                df_to_save["trade_date"] = df_to_save["trade_date"].dt.strftime("%Y%m%d")

            # 保存前再次固定列顺序
            available_columns = [col for col in STOCK_DAILY_COLUMNS if col in df_to_save.columns]
            df_to_save = df_to_save[available_columns]

            file_path = output_dir / f"{ts_code}_{start_date}_{end_date}.csv"
            df_to_save.to_csv(file_path, index=False, encoding="utf-8-sig")
            TushareDownloader._cleanup_old_csv_files(ts_code, output_dir, file_path)
            saved_files.append(file_path)
            logger.info(f"已保存 {ts_code} 数据到: {file_path}")

        logger.info(f"完成CSV保存，共 {len(saved_files)} 个文件")
        return saved_files

    @staticmethod
    def _cleanup_old_csv_files(ts_code: str, output_dir: Path, keep_file: Path) -> None:
        """删除同一股票的旧CSV文件，只保留最新文件"""
        for old_file in output_dir.glob(f"{ts_code}_*.csv"):
            if old_file != keep_file:
                try:
                    old_file.unlink()
                except Exception as e:
                    logger.warning(f"删除旧文件失败: {old_file}, 错误: {e}")

    def get_all_stock_basic(self) -> Optional[pd.DataFrame]:
        """
        获取全市场股票基础信息（上市/退市/暂停）

        Returns:
            DataFrame，字段为 STOCK_BASIC_COLUMNS
        """
        all_frames = []
        for list_status in ["L", "D", "P"]:
            df = None
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    df = self.pro.stock_basic(
                        exchange="",
                        list_status=list_status,
                        fields=",".join(STOCK_BASIC_COLUMNS),
                    )
                    break
                except Exception as e:
                    logger.warning(
                        f"第 {attempt + 1} 次获取 stock_basic(list_status={list_status}) 失败: {e}"
                    )
                    if attempt == RETRY_ATTEMPTS - 1:
                        raise

            if df is not None and not df.empty:
                all_frames.append(df)

        if not all_frames:
            logger.warning("未获取到任何股票基础信息")
            return None

        merged = pd.concat(all_frames, ignore_index=True)
        merged = merged.drop_duplicates(subset=["ts_code"], keep="first")

        for col in ["list_date", "delist_date"]:
            if col in merged.columns:
                merged[col] = merged[col].fillna("").astype(str)

        for col in STOCK_BASIC_COLUMNS:
            if col not in merged.columns:
                merged[col] = ""

        merged = merged[STOCK_BASIC_COLUMNS].sort_values("ts_code").reset_index(drop=True)
        logger.info(f"获取股票基础信息成功，共 {len(merged)} 条")
        return merged

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """
        获取指定交易日的股票指标（daily_basic）
        """
        df = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                df = self.pro.daily_basic(
                    trade_date=trade_date,
                    fields=",".join(DAILY_BASIC_COLUMNS),
                )
                break
            except Exception as e:
                logger.warning(
                    f"第 {attempt + 1} 次获取 daily_basic({trade_date}) 失败: {e}"
                )
                if attempt == RETRY_ATTEMPTS - 1:
                    raise

        if df is None or df.empty:
            logger.warning(f"{trade_date} 未获取到 daily_basic 数据")
            return None

        for col in DAILY_BASIC_COLUMNS:
            if col not in df.columns:
                df[col] = None

        df = df[DAILY_BASIC_COLUMNS].sort_values("ts_code").reset_index(drop=True)
        logger.info(f"获取 {trade_date} daily_basic 成功，共 {len(df)} 条")
        return df

    def get_latest_daily_basic(self, end_date: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        获取截至 end_date 的最近一个有数据的交易日 daily_basic
        """
        recent_days = pd.date_range(end=pd.to_datetime(end_date), periods=15, freq="D")
        for day in sorted(recent_days.strftime("%Y%m%d"), reverse=True):
            df = self.get_daily_basic(day)
            if df is not None and not df.empty:
                return df, day
        return None, None

    def get_open_trade_dates(self, start_date: str, end_date: str, exchange: str = "SSE") -> List[str]:
        """
        获取区间内开市交易日列表
        """
        df = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                df = self.pro.trade_cal(
                    exchange=exchange,
                    start_date=start_date,
                    end_date=end_date,
                    fields="exchange,cal_date,is_open",
                )
                break
            except Exception as e:
                logger.warning(
                    f"第 {attempt + 1} 次获取 trade_cal({start_date}-{end_date}) 失败: {e}"
                )
                if attempt == RETRY_ATTEMPTS - 1:
                    raise

        if df is None or df.empty:
            return []

        open_days = (
            df[df["is_open"] == 1]["cal_date"]
            .astype(str)
            .sort_values()
            .tolist()
        )
        return open_days

    def get_daily_snapshot(self, trade_date: str) -> Optional[pd.DataFrame]:
        """
        获取指定交易日全市场 daily 数据
        """
        df = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                df = self.pro.daily(
                    trade_date=trade_date,
                    fields=",".join(STOCK_DAILY_COLUMNS),
                )
                break
            except Exception as e:
                logger.warning(
                    f"第 {attempt + 1} 次获取 daily({trade_date}) 失败: {e}"
                )
                if attempt == RETRY_ATTEMPTS - 1:
                    raise

        if df is None:
            return None

        for col in STOCK_DAILY_COLUMNS:
            if col not in df.columns:
                df[col] = None

        normalized = self._normalize_daily_df(df)
        if not normalized.empty:
            normalized["trade_date"] = normalized["trade_date"].dt.strftime("%Y%m%d")
        return normalized

    @staticmethod
    def save_stock_basic_csv(
        stock_basic_df: pd.DataFrame,
        output_file: Path = DATA_DIR / "all_stocks.csv",
    ) -> Path:
        """
        保存股票基础信息为CSV
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        stock_basic_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        logger.info(f"股票基础信息已保存: {output_file}")
        return output_file

    @staticmethod
    def save_daily_basic_csv(
        daily_basic_df: pd.DataFrame,
        output_file: Path,
    ) -> Path:
        """
        保存 daily_basic 到CSV
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        daily_basic_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        logger.info(f"daily_basic 已保存: {output_file}")
        return output_file

    @staticmethod
    def save_daily_snapshot_csv(
        daily_df: pd.DataFrame,
        trade_date: str,
        output_dir: Path = DAILY_HISTORY_DIR,
    ) -> Path:
        """
        保存指定交易日的全市场 daily 快照
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"daily_{trade_date}.csv"
        daily_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        logger.info(f"daily快照已保存: {output_file}")
        return output_file
