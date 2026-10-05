from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_COLUMNS = [
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
]

COLUMN_MAP = {
    "Invoice": "invoice_no",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_timestamp",
    "Price": "unit_price",
    "Customer ID": "customer_id",
    "Country": "country",
}

BUSINESS_COLUMNS = list(COLUMN_MAP.values())


def load_source_workbook(path: Path) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Load every worksheet and attach stable source-line lineage."""
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    if not sheets:
        raise ValueError(f"Workbook has no worksheets: {path}")

    frames: list[pd.DataFrame] = []
    for sheet_name, frame in sheets.items():
        missing = [column for column in SOURCE_COLUMNS if column not in frame.columns]
        extra = [column for column in frame.columns if column not in SOURCE_COLUMNS]
        if missing or extra:
            raise ValueError(
                f"Unexpected schema in sheet {sheet_name!r}. "
                f"Missing={missing}; extra={extra}"
            )
        current = frame[SOURCE_COLUMNS].copy()
        current["source_sheet"] = sheet_name
        current["source_row_number"] = np.arange(2, len(current) + 2, dtype="int64")
        frames.append(current)

    return sheets, pd.concat(frames, ignore_index=True)


def with_standard_column_names(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rename(columns=COLUMN_MAP).copy()


def normalize_identifier(series: pd.Series, uppercase: bool = True) -> pd.Series:
    result = series.astype("string").str.strip()
    result = result.str.replace(r"\.0+$", "", regex=True)
    result = result.mask(result.eq(""), pd.NA)
    return result.str.upper() if uppercase else result


def normalize_text(series: pd.Series, uppercase: bool = False) -> pd.Series:
    result = series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    result = result.mask(result.eq(""), pd.NA)
    return result.str.upper() if uppercase else result


def json_safe(value: Any) -> Any:
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
