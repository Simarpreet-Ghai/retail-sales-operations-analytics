from __future__ import annotations

import numpy as np
import pandas as pd


def build_star_schema(cleaned: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sales = cleaned.loc[cleaned["record_status"].eq("SALE")].copy()
    sales["sale_date"] = sales["invoice_timestamp"].dt.normalize()

    dates = pd.date_range(sales["sale_date"].min(), sales["sale_date"].max(), freq="D")
    dim_date = pd.DataFrame({"date": dates})
    dim_date["date_key"] = dim_date["date"].dt.strftime("%Y%m%d").astype("int64")
    dim_date["day"] = dim_date["date"].dt.day
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["month_name"] = dim_date["date"].dt.month_name()
    dim_date["quarter"] = dim_date["date"].dt.quarter
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["weekday_name"] = dim_date["date"].dt.day_name()
    dim_date["is_weekend"] = dim_date["date"].dt.dayofweek.ge(5)
    dim_date = dim_date[
        [
            "date_key",
            "date",
            "day",
            "month",
            "month_name",
            "quarter",
            "year",
            "weekday_name",
            "is_weekend",
        ]
    ]

    product_dates = sales.groupby("stock_code", as_index=False).agg(
        first_sale_date=("sale_date", "min"), last_sale_date=("sale_date", "max")
    )
    latest_product = (
        sales.sort_values(["invoice_timestamp", "source_sheet", "source_row_number"])
        .drop_duplicates("stock_code", keep="last")
        [["stock_code", "description"]]
        .rename(columns={"description": "product_description"})
    )
    dim_product = latest_product.merge(product_dates, on="stock_code", how="inner")
    dim_product = dim_product.sort_values("stock_code").reset_index(drop=True)
    dim_product.insert(0, "product_key", np.arange(1, len(dim_product) + 1, dtype="int64"))

    customer_ids = sorted(sales["customer_id"].dropna().unique().tolist())
    dim_customer = pd.DataFrame(
        {
            "customer_key": np.arange(1, len(customer_ids) + 1, dtype="int64"),
            "customer_id": customer_ids,
            "customer_type": "IDENTIFIED",
        }
    )
    dim_customer = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "customer_key": 0,
                        "customer_id": "[UNKNOWN]",
                        "customer_type": "ANONYMOUS",
                    }
                ]
            ),
            dim_customer,
        ],
        ignore_index=True,
    )

    countries = sorted(sales["country"].dropna().unique().tolist())
    dim_location = pd.DataFrame(
        {
            "location_key": np.arange(1, len(countries) + 1, dtype="int64"),
            "country": countries,
        }
    )

    fact = sales.merge(
        dim_product[["product_key", "stock_code"]],
        on="stock_code",
        how="left",
        validate="many_to_one",
    )
    fact = fact.merge(
        dim_customer[["customer_key", "customer_id"]],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )
    fact["customer_key"] = fact["customer_key"].fillna(0).astype("int64")
    fact = fact.merge(dim_location, on="country", how="left", validate="many_to_one")
    fact["date_key"] = fact["sale_date"].dt.strftime("%Y%m%d").astype("int64")
    fact_sales = fact[
        [
            "source_line_id",
            "invoice_no",
            "invoice_timestamp",
            "date_key",
            "customer_key",
            "product_key",
            "location_key",
            "quantity",
            "unit_price",
            "line_revenue",
        ]
    ].rename(columns={"source_line_id": "sales_line_id", "line_revenue": "revenue"})

    return {
        "dim_date": dim_date,
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_location": dim_location,
        "fact_sales": fact_sales,
    }
