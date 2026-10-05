from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingest import write_json


EXPECTED = {
    "original_rows": 1_067_371,
    "cleaned_staging_rows": 1_033_036,
    "analytical_sales_rows": 1_007_913,
    "orders": 40_077,
    "identified_customers": 5_878,
    "products": 4_745,
    "date_min": "2009-12-01",
    "date_max": "2011-12-09",
    "total_revenue_gbp": 20_476_260.45,
    "units_sold": 11_205_148,
    "average_order_value_gbp": 510.92,
    "duplicates_removed": 34_335,
    "repeat_customer_rate": 0.723886,
    "repeat_customers": 4_255,
    "uk_revenue_gbp": 17_410_196.12,
    "uk_revenue_share": 0.850262,
    "top_10_customer_share": 0.136113,
    "top_10_product_share": 0.103197,
    "peak_month": "2011-11-01",
    "peak_month_revenue_gbp": 1_503_866.78,
    "peak_month_orders": 2_769,
}


def _check(name: str, actual, expected, tolerance: float = 0) -> dict:
    if tolerance:
        passed = abs(float(actual) - float(expected)) <= tolerance
    else:
        passed = str(actual) == str(expected)
    return {
        "check": name,
        "actual": actual,
        "expected": expected,
        "tolerance": tolerance,
        "status": "PASS" if passed else "FAIL",
    }


def reconcile_verified_baseline(
    profile: dict,
    cleaning: dict,
    database_manifest: dict,
    results: dict[str, pd.DataFrame],
    output_dir: Path,
) -> pd.DataFrame:
    core = results["01_core_kpis"].iloc[0]
    countries = results["03_country_performance"]
    uk = countries.loc[countries["country"].eq("United Kingdom")].iloc[0]
    concentration = results["06_revenue_concentration"].iloc[0]
    repeat = results["07_repeat_customers"].iloc[0]
    monthly = results["02_monthly_revenue"]
    peak = monthly.loc[monthly["complete_month"]].sort_values("revenue", ascending=False).iloc[0]

    checks = [
        _check("original_rows", profile["source"]["original_row_count"], EXPECTED["original_rows"]),
        _check("cleaned_staging_rows", cleaning["cleaned_staging_row_count"], EXPECTED["cleaned_staging_rows"]),
        _check("analytical_sales_rows", database_manifest["table_row_counts"]["fact_sales"], EXPECTED["analytical_sales_rows"]),
        _check("orders", int(core["total_orders"]), EXPECTED["orders"]),
        _check("identified_customers", int(core["unique_identified_customers"]), EXPECTED["identified_customers"]),
        _check("products", database_manifest["table_row_counts"]["dim_product"], EXPECTED["products"]),
        _check(
            "date_min",
            str(pd.Timestamp(core["sales_date_min"]).date()),
            EXPECTED["date_min"],
        ),
        _check(
            "date_max",
            str(pd.Timestamp(core["sales_date_max"]).date()),
            EXPECTED["date_max"],
        ),
        _check("total_revenue_gbp", core["total_revenue_gbp"], EXPECTED["total_revenue_gbp"], 0.01),
        _check("units_sold", int(core["units_sold"]), EXPECTED["units_sold"]),
        _check("average_order_value_gbp", core["average_order_value_gbp"], EXPECTED["average_order_value_gbp"], 0.01),
        _check("duplicates_removed", cleaning["duplicate_rows_removed"], EXPECTED["duplicates_removed"]),
        _check("repeat_customer_rate", repeat["repeat_customer_rate"], EXPECTED["repeat_customer_rate"], 0.000001),
        _check("repeat_customers", int(repeat["repeat_customers"]), EXPECTED["repeat_customers"]),
        _check("uk_revenue_gbp", uk["revenue"], EXPECTED["uk_revenue_gbp"], 0.01),
        _check("uk_revenue_share", uk["revenue_share"], EXPECTED["uk_revenue_share"], 0.000001),
        _check("top_10_customer_share", concentration["top_10_customer_share"], EXPECTED["top_10_customer_share"], 0.000001),
        _check("top_10_product_share", concentration["top_10_product_share"], EXPECTED["top_10_product_share"], 0.000001),
        _check(
            "peak_month",
            str(pd.Timestamp(peak["month_start"]).date()),
            EXPECTED["peak_month"],
        ),
        _check("peak_month_revenue_gbp", peak["revenue"], EXPECTED["peak_month_revenue_gbp"], 0.01),
        _check("peak_month_orders", int(peak["orders"]), EXPECTED["peak_month_orders"]),
    ]
    frame = pd.DataFrame(checks)
    frame.to_csv(output_dir / "baseline_reconciliation.csv", index=False)
    failed = frame.loc[frame["status"].ne("PASS")]
    write_json(
        output_dir / "baseline_reconciliation.json",
        {
            "checks_executed": int(len(frame)),
            "checks_passed": int(frame["status"].eq("PASS").sum()),
            "checks_failed": int(len(failed)),
            "status": "PASS" if failed.empty else "FAIL",
            "failed_checks": failed.to_dict("records"),
        },
    )
    if not failed.empty:
        raise RuntimeError(
            "Verified baseline reconciliation failed:\n" + failed.to_string(index=False)
        )
    return frame
