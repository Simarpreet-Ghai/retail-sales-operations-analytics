from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest import (
    BUSINESS_COLUMNS,
    normalize_identifier,
    normalize_text,
    with_standard_column_names,
    write_json,
)


CLEAN_COLUMNS = [
    "source_line_id",
    "source_sheet",
    "source_row_number",
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_timestamp",
    "unit_price",
    "customer_id",
    "country",
    "line_revenue",
    "cancellation_flag",
    "return_flag",
    "invalid_quantity_flag",
    "invalid_price_flag",
    "missing_required_flag",
    "customer_missing_flag",
    "description_missing_flag",
    "record_status",
]


def clean_source(combined_source: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frame = with_standard_column_names(combined_source)
    starting_rows = len(frame)

    frame["invoice_no"] = normalize_identifier(frame["invoice_no"])
    frame["stock_code"] = normalize_identifier(frame["stock_code"])
    frame["customer_id"] = normalize_identifier(frame["customer_id"], uppercase=False)
    frame["description"] = normalize_text(frame["description"], uppercase=True)
    frame["country"] = normalize_text(frame["country"])
    frame["invoice_timestamp"] = pd.to_datetime(frame["invoice_timestamp"], errors="coerce")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce")

    duplicate_mask = frame.duplicated(subset=BUSINESS_COLUMNS, keep="first")
    duplicate_rows_removed = int(duplicate_mask.sum())
    frame = frame.loc[~duplicate_mask].copy()

    non_integer_quantity = frame["quantity"].notna() & frame["quantity"].mod(1).ne(0)
    frame["cancellation_flag"] = frame["invoice_no"].str.startswith("C", na=False)
    frame["return_flag"] = frame["quantity"].lt(0).fillna(False)
    frame["invalid_quantity_flag"] = (
        frame["quantity"].isna() | frame["quantity"].le(0) | non_integer_quantity
    )
    frame["invalid_price_flag"] = frame["unit_price"].isna() | frame["unit_price"].le(0)
    frame["missing_required_flag"] = frame[
        ["invoice_no", "stock_code", "invoice_timestamp", "country"]
    ].isna().any(axis=1)
    frame["customer_missing_flag"] = frame["customer_id"].isna()
    frame["description_missing_flag"] = frame["description"].isna()
    description_missing_count = int(frame["description_missing_flag"].sum())
    frame["description"] = frame["description"].fillna("[NO DESCRIPTION]")

    frame["record_status"] = np.select(
        [
            frame["cancellation_flag"],
            frame["return_flag"],
            frame["missing_required_flag"],
            frame["invalid_quantity_flag"],
            frame["invalid_price_flag"],
        ],
        [
            "CANCELLATION",
            "RETURN",
            "MISSING_REQUIRED",
            "INVALID_QUANTITY",
            "INVALID_PRICE",
        ],
        default="SALE",
    )
    frame["line_revenue"] = (frame["quantity"] * frame["unit_price"]).round(4)
    frame["source_line_id"] = (
        frame["source_sheet"].astype("string")
        + ":"
        + frame["source_row_number"].astype("string")
    )

    sales = frame.loc[frame["record_status"].eq("SALE")]
    status_counts = frame["record_status"].value_counts().sort_index().to_dict()
    summary = {
        "starting_row_count": int(starting_rows),
        "duplicate_rows_removed": duplicate_rows_removed,
        "cleaned_staging_row_count": int(len(frame)),
        "analytical_sales_row_count": int(len(sales)),
        "excluded_from_analytical_sales": int(len(frame) - len(sales)),
        "description_values_imputed": description_missing_count,
        "customer_ids_left_missing": int(frame["customer_missing_flag"].sum()),
        "cancellation_rows": int(frame["cancellation_flag"].sum()),
        "return_rows": int(frame["return_flag"].sum()),
        "invalid_quantity_rows": int(frame["invalid_quantity_flag"].sum()),
        "invalid_price_rows": int(frame["invalid_price_flag"].sum()),
        "missing_required_rows": int(frame["missing_required_flag"].sum()),
        "record_status_counts": {str(key): int(value) for key, value in status_counts.items()},
        "sales_date_min": sales["invoice_timestamp"].min(),
        "sales_date_max": sales["invoice_timestamp"].max(),
        "sales_revenue": float(sales["line_revenue"].sum()),
    }
    return frame[CLEAN_COLUMNS], summary


def save_cleaned_data(
    processed_dir: Path, output_dir: Path, cleaned: pd.DataFrame, summary: dict
) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(
        processed_dir / "online_retail_clean.csv.gz",
        index=False,
        compression="gzip",
        date_format="%Y-%m-%d %H:%M:%S",
    )
    cleaned.loc[cleaned["record_status"].ne("SALE")].to_csv(
        processed_dir / "online_retail_exceptions.csv.gz",
        index=False,
        compression="gzip",
        date_format="%Y-%m-%d %H:%M:%S",
    )
    write_json(output_dir / "cleaning_summary.json", summary)
