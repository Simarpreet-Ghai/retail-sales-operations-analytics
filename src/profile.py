from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingest import (
    BUSINESS_COLUMNS,
    SOURCE_COLUMNS,
    with_standard_column_names,
    write_json,
)


def build_profile(
    source_sheets: dict[str, pd.DataFrame], combined_source: pd.DataFrame
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    frame = with_standard_column_names(combined_source)
    invoice = frame["invoice_no"].astype("string").str.strip().str.upper()
    stock_code = frame["stock_code"].astype("string").str.strip().str.upper()
    quantity = pd.to_numeric(frame["quantity"], errors="coerce")
    price = pd.to_numeric(frame["unit_price"], errors="coerce")
    invoice_timestamp = pd.to_datetime(frame["invoice_timestamp"], errors="coerce")

    exact_duplicate_mask = frame.duplicated(subset=BUSINESS_COLUMNS, keep=False)
    exact_duplicate_extra_mask = frame.duplicated(subset=BUSINESS_COLUMNS, keep="first")
    invoice_counts = invoice.dropna().value_counts()
    invoice_product_counts = (
        pd.DataFrame({"invoice_no": invoice, "stock_code": stock_code})
        .dropna()
        .value_counts()
    )

    missing = frame[BUSINESS_COLUMNS].isna().sum().rename("missing_count").to_frame()
    missing["missing_pct"] = missing["missing_count"] / len(frame)
    missing = missing.reset_index(names="column")

    sheet_rows: list[dict] = []
    for sheet_name, source in source_sheets.items():
        dates = pd.to_datetime(source["InvoiceDate"], errors="coerce")
        sheet_rows.append(
            {
                "sheet_name": sheet_name,
                "row_count": int(len(source)),
                "column_count": int(source.shape[1]),
                "date_min": dates.min(),
                "date_max": dates.max(),
            }
        )

    customer = frame["customer_id"].astype("string").str.strip()
    country = frame["country"].astype("string").str.strip()
    cancellation = invoice.str.startswith("C", na=False)
    profile = {
        "source": {
            "file_name": "online_retail_II.xlsx",
            "sheet_names": list(source_sheets),
            "original_row_count": int(len(frame)),
            "column_count": len(SOURCE_COLUMNS),
            "columns": SOURCE_COLUMNS,
            "sheet_dtypes": {
                name: {column: str(dtype) for column, dtype in source.dtypes.items()}
                for name, source in source_sheets.items()
            },
        },
        "coverage": {
            "date_min": invoice_timestamp.min(),
            "date_max": invoice_timestamp.max(),
            "unique_invoices": int(invoice.nunique(dropna=True)),
            "unique_customers": int(customer.nunique(dropna=True)),
            "unique_products": int(stock_code.nunique(dropna=True)),
            "unique_countries": int(country.nunique(dropna=True)),
        },
        "quality": {
            "exact_duplicate_rows_including_first": int(exact_duplicate_mask.sum()),
            "exact_duplicate_extra_rows": int(exact_duplicate_extra_mask.sum()),
            "invoices_with_multiple_lines": int((invoice_counts > 1).sum()),
            "invoice_product_pairs_with_multiple_lines": int(
                (invoice_product_counts > 1).sum()
            ),
            "rows_in_repeated_invoice_product_pairs": int(
                invoice_product_counts[invoice_product_counts > 1].sum()
            ),
            "missing_values": {
                row["column"]: int(row["missing_count"])
                for row in missing.to_dict("records")
            },
            "quantity_missing_or_non_numeric": int(quantity.isna().sum()),
            "quantity_zero": int(quantity.eq(0).sum()),
            "quantity_negative": int(quantity.lt(0).sum()),
            "price_missing_or_non_numeric": int(price.isna().sum()),
            "price_zero": int(price.eq(0).sum()),
            "price_negative": int(price.lt(0).sum()),
            "cancellation_rows": int(cancellation.sum()),
            "cancellation_invoices": int(invoice[cancellation].nunique()),
            "negative_quantity_non_cancellation_rows": int(
                (quantity.lt(0) & ~cancellation).sum()
            ),
            "positive_quantity_cancellation_rows": int(
                (quantity.gt(0) & cancellation).sum()
            ),
            "invalid_dates": int(invoice_timestamp.isna().sum()),
        },
    }
    return profile, missing, pd.DataFrame(sheet_rows)


def save_profile(
    output_dir: Path,
    profile: dict,
    missing: pd.DataFrame,
    sheet_profile: pd.DataFrame,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_profile.json", profile)
    missing.to_csv(output_dir / "missing_values.csv", index=False)
    sheet_profile.to_csv(output_dir / "sheet_profile.csv", index=False)

    source = profile["source"]
    coverage = profile["coverage"]
    quality = profile["quality"]
    lines = [
        "# Raw data profile",
        "",
        f"- Rows: {source['original_row_count']:,}",
        f"- Columns: {source['column_count']}",
        f"- Date range: {coverage['date_min'].date()} to {coverage['date_max'].date()}",
        f"- Unique invoices: {coverage['unique_invoices']:,}",
        f"- Unique customers: {coverage['unique_customers']:,}",
        f"- Unique stock codes: {coverage['unique_products']:,}",
        f"- Countries: {coverage['unique_countries']:,}",
        f"- Exact duplicate extra rows: {quality['exact_duplicate_extra_rows']:,}",
        f"- Cancellation rows: {quality['cancellation_rows']:,}",
        f"- Negative-quantity rows: {quality['quantity_negative']:,}",
        f"- Zero-price rows: {quality['price_zero']:,}",
        f"- Negative-price rows: {quality['price_negative']:,}",
        "",
        "Invoice numbers repeat because the source grain is an invoice line, not an order.",
    ]
    (output_dir / "profile_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
