from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingest import write_json


def _number(value) -> float:
    return float(value)


def save_business_outputs(
    output_dir: Path, results: dict[str, pd.DataFrame]
) -> tuple[dict, list[dict]]:
    core = results["01_core_kpis"].iloc[0]
    monthly = results["02_monthly_revenue"]
    countries = results["03_country_performance"]
    concentration = results["06_revenue_concentration"].iloc[0]
    repeat = results["07_repeat_customers"].iloc[0]

    kpis = {
        "total_revenue_gbp": _number(core["total_revenue_gbp"]),
        "total_orders": int(core["total_orders"]),
        "units_sold": int(core["units_sold"]),
        "unique_identified_customers": int(core["unique_identified_customers"]),
        "average_order_value_gbp": _number(core["average_order_value_gbp"]),
        "revenue_per_identified_customer_gbp": _number(
            core["revenue_per_identified_customer_gbp"]
        ),
        "repeat_customer_rate": _number(core["repeat_customer_rate"]),
        "anonymous_revenue_share": _number(core["anonymous_revenue_share"]),
    }

    top_country = countries.iloc[0]
    complete_months = monthly.loc[monthly["complete_month"]]
    peak_month = complete_months.loc[complete_months["revenue"].astype(float).idxmax()]
    findings = [
        {
            "finding_id": "geographic_concentration",
            "what": f"{top_country['country']} generated the largest share of observed valid revenue.",
            "metric": _number(top_country["revenue_share"]),
            "metric_display": f"{_number(top_country['revenue_share']):.1%} of valid revenue (£{_number(top_country['revenue']):,.2f}).",
            "sql_query": "sql/analysis/03_country_performance.sql",
            "business_relevance": "The observed revenue base is geographically concentrated, so country-level performance can materially affect total results.",
            "limitation": "Country is the customer country recorded on the invoice; it does not establish nationality or shipment profitability.",
        },
        {
            "finding_id": "customer_concentration",
            "what": "The ten highest-revenue identified customers generated a measurable share of total valid revenue.",
            "metric": _number(concentration["top_10_customer_share"]),
            "metric_display": f"{_number(concentration['top_10_customer_share']):.1%} of valid revenue (£{_number(concentration['top_10_customer_revenue']):,.2f}).",
            "sql_query": "sql/analysis/06_revenue_concentration.sql",
            "business_relevance": "A concentrated customer base makes retention of a small group commercially important.",
            "limitation": "Missing customer IDs are excluded from the ranking but their revenue remains in the denominator.",
        },
        {
            "finding_id": "product_concentration",
            "what": "The ten highest-revenue stock codes generated a limited share of total valid revenue.",
            "metric": _number(concentration["top_10_product_share"]),
            "metric_display": f"{_number(concentration['top_10_product_share']):.1%} of valid revenue (£{_number(concentration['top_10_product_revenue']):,.2f}).",
            "sql_query": "sql/analysis/06_revenue_concentration.sql",
            "business_relevance": "The result shows how dependent revenue is on a small group of items or invoice charge codes.",
            "limitation": "The source has no product category and includes non-merchandise codes such as postage or adjustments.",
        },
        {
            "finding_id": "repeat_customers",
            "what": "A majority of identified customers placed at least two valid sales invoices.",
            "metric": _number(repeat["repeat_customer_rate"]),
            "metric_display": f"{_number(repeat['repeat_customer_rate']):.1%}: {int(repeat['repeat_customers']):,} of {int(repeat['identified_customers']):,} identified customers.",
            "sql_query": "sql/analysis/07_repeat_customers.sql",
            "business_relevance": "Repeat purchasing is an observable retention indicator for the identified-customer population.",
            "limitation": "Anonymous customers are excluded, and the metric is limited to the observation window.",
        },
        {
            "finding_id": "peak_month",
            "what": f"{pd.Timestamp(peak_month['month_start']):%B %Y} was the highest-revenue complete calendar month.",
            "metric": _number(peak_month["revenue"]),
            "metric_display": f"£{_number(peak_month['revenue']):,.2f} across {int(peak_month['orders']):,} valid sales invoices.",
            "sql_query": "sql/analysis/02_monthly_revenue.sql",
            "business_relevance": "The monthly pattern provides a factual starting point for capacity and inventory planning.",
            "limitation": "The dataset has no promotion, inventory, margin, or causal demand-driver fields.",
        },
    ]

    write_json(output_dir / "kpis.json", kpis)
    write_json(output_dir / "business_findings.json", findings)
    lines = ["# Verified business findings", ""]
    for index, finding in enumerate(findings, start=1):
        lines.extend(
            [
                f"## {index}. {finding['what']}",
                "",
                f"- Metric: {finding['metric_display']}",
                f"- Executed SQL: `{finding['sql_query']}`",
                f"- Business relevance: {finding['business_relevance']}",
                f"- Limitation: {finding['limitation']}",
                "",
            ]
        )
    (output_dir / "business_findings.md").write_text("\n".join(lines), encoding="utf-8")
    return kpis, findings
