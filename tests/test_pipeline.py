from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.clean import clean_source
from src.database import (
    build_database,
    export_powerbi_tables,
    run_analysis,
    run_validation,
)
from src.model import build_star_schema


@pytest.fixture
def source() -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            ["100", "a", " Product A ", 2, "2020-01-01 10:00", 3.5, 1, " UK "],
            ["100", "a", " Product A ", 2, "2020-01-01 10:00", 3.5, 1, " UK "],
            ["C101", "a", "Product A", -1, "2020-01-02 10:00", 3.5, 1, "UK"],
            ["102", "b", None, 1, "2020-01-03 10:00", 0, None, "UK"],
            ["103", "c", "Product C", 4, "2020-01-04 10:00", 2.0, None, "France"],
            ["104", "d", "Product D", 1, "2020-01-05 10:00", 4.0, 2, "UK"],
            ["105", "c", "Product C", 1, "2020-01-06 10:00", 2.0, 1, "France"],
        ],
        columns=[
            "Invoice",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "Price",
            "Customer ID",
            "Country",
        ],
    )
    frame["source_sheet"] = "Test"
    frame["source_row_number"] = range(2, len(frame) + 2)
    return frame


@pytest.fixture
def cleaned(source: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    return clean_source(source)


def test_cleaning_deduplicates_exact_business_rows(cleaned) -> None:
    frame, summary = cleaned
    assert summary["starting_row_count"] == 7
    assert summary["duplicate_rows_removed"] == 1
    assert len(frame) == 6


def test_cleaning_classifies_exceptions(cleaned) -> None:
    frame, summary = cleaned
    assert summary["analytical_sales_row_count"] == 4
    assert frame["record_status"].value_counts().to_dict() == {
        "SALE": 4,
        "CANCELLATION": 1,
        "INVALID_PRICE": 1,
    }


def test_cleaning_normalizes_text_and_calculates_revenue(cleaned) -> None:
    frame, _ = cleaned
    row = frame.loc[frame["invoice_no"].eq("100")].iloc[0]
    assert row["stock_code"] == "A"
    assert row["description"] == "PRODUCT A"
    assert row["country"] == "UK"
    assert row["line_revenue"] == pytest.approx(7.0)


def test_star_schema_uses_unknown_customer_key(cleaned) -> None:
    frame, _ = cleaned
    tables = build_star_schema(frame)
    assert tables["dim_customer"].iloc[0].to_dict() == {
        "customer_key": 0,
        "customer_id": "[UNKNOWN]",
        "customer_type": "ANONYMOUS",
    }
    assert tables["fact_sales"]["customer_key"].eq(0).sum() == 1


def test_star_schema_has_expected_grain_and_dimensions(cleaned) -> None:
    frame, summary = cleaned
    tables = build_star_schema(frame)
    assert len(tables["fact_sales"]) == summary["analytical_sales_row_count"]
    assert tables["fact_sales"]["sales_line_id"].is_unique
    assert tables["dim_product"]["stock_code"].is_unique
    assert tables["dim_location"]["country"].is_unique
    assert len(tables["dim_date"]) == 6


@pytest.fixture
def built_database(tmp_path: Path, cleaned) -> tuple[Path, Path, dict]:
    frame, summary = cleaned
    database_path = tmp_path / "test.duckdb"
    output_dir = tmp_path / "outputs"
    root = Path(__file__).resolve().parents[1]
    manifest = build_database(
        database_path,
        root / "sql/schema.sql",
        frame,
        build_star_schema(frame),
        summary,
    )
    return database_path, output_dir, manifest


def test_database_build_creates_all_model_tables(built_database) -> None:
    database_path, _, manifest = built_database
    assert manifest["table_row_counts"]["fact_sales"] == 4
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    finally:
        connection.close()
    assert {
        "pipeline_audit",
        "staging_clean",
        "dim_date",
        "dim_customer",
        "dim_product",
        "dim_location",
        "fact_sales",
    } <= tables


def test_all_duckdb_model_validations_pass(built_database) -> None:
    database_path, output_dir, _ = built_database
    root = Path(__file__).resolve().parents[1]
    result = run_validation(
        database_path,
        root / "sql/validation/model_checks.sql",
        output_dir,
    )
    assert len(result) == 20
    assert result["status"].eq("PASS").all()


def test_all_eight_analysis_queries_execute(built_database) -> None:
    database_path, output_dir, _ = built_database
    root = Path(__file__).resolve().parents[1]
    results, manifest = run_analysis(
        database_path,
        root / "sql/analysis",
        output_dir,
    )
    assert manifest["queries_executed"] == 8
    assert set(results) == {
        "01_core_kpis",
        "02_monthly_revenue",
        "03_country_performance",
        "04_product_performance",
        "05_customer_performance",
        "06_revenue_concentration",
        "07_repeat_customers",
        "08_yearly_order_behavior",
    }
    core = results["01_core_kpis"].iloc[0]
    assert int(core["total_orders"]) == 4
    assert float(core["total_revenue_gbp"]) == pytest.approx(21.0)


def test_powerbi_exports_match_database_counts(built_database, tmp_path: Path) -> None:
    database_path, _, manifest = built_database
    export_dir = tmp_path / "powerbi"
    counts = export_powerbi_tables(database_path, export_dir)
    assert counts == {
        table: manifest["table_row_counts"][table]
        for table in [
            "fact_sales",
            "dim_date",
            "dim_customer",
            "dim_product",
            "dim_location",
        ]
    }
    assert all((export_dir / f"{table}.csv").exists() for table in counts)
