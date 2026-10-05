from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import save_business_outputs
from src.clean import clean_source, save_cleaned_data
from src.database import (
    build_database,
    export_powerbi_tables,
    run_analysis,
    run_validation,
)
from src.ingest import load_source_workbook, write_json
from src.model import build_star_schema
from src.profile import build_profile, save_profile
from src.validate import reconcile_verified_baseline


EXPECTED_SOURCE_SHA256 = (
    "bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(root: Path) -> dict:
    source_path = root / "data/raw/online_retail_II.xlsx"
    output_dir = root / "outputs"
    processed_dir = root / "data/processed"
    database_path = root / "data/analytics/retail_analytics.duckdb"
    powerbi_dir = root / "data/powerbi"

    source_hash = sha256(source_path)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            "Source workbook SHA-256 does not match the verified project source. "
            f"Expected {EXPECTED_SOURCE_SHA256}; got {source_hash}."
        )

    print("1/8 Loading and profiling both workbook sheets...")
    sheets, source = load_source_workbook(source_path)
    profile, missing, sheet_profile = build_profile(sheets, source)
    profile["source"]["sha256"] = source_hash
    save_profile(output_dir, profile, missing, sheet_profile)

    print("2/8 Cleaning, classifying, and de-duplicating invoice lines...")
    cleaned, cleaning = clean_source(source)
    save_cleaned_data(processed_dir, output_dir, cleaned, cleaning)

    print("3/8 Building the star-schema data frames...")
    model_tables = build_star_schema(cleaned)

    print("4/8 Creating the DuckDB database and loading six model tables...")
    database_manifest = build_database(
        database_path,
        root / "sql/schema.sql",
        cleaned,
        model_tables,
        cleaning,
    )
    database_manifest["source_sha256"] = source_hash
    write_json(output_dir / "duckdb_database_manifest.json", database_manifest)

    print("5/8 Running all DuckDB model validations...")
    validation = run_validation(
        database_path,
        root / "sql/validation/model_checks.sql",
        output_dir,
    )

    print("6/8 Executing all eight analytical SQL files...")
    results, analysis_manifest = run_analysis(
        database_path,
        root / "sql/analysis",
        output_dir,
    )
    save_business_outputs(output_dir, results)

    print("7/8 Reconciling executed results to the verified local baseline...")
    baseline = reconcile_verified_baseline(
        profile,
        cleaning,
        database_manifest,
        results,
        output_dir,
    )

    print("8/8 Exporting the five Power BI-ready CSV tables...")
    export_counts = export_powerbi_tables(database_path, powerbi_dir)
    powerbi_manifest = {
        "status": "CSV_EXPORT_COMPLETE",
        "power_bi_desktop_status": "NOT_EXECUTED",
        "tables": {
            table: {
                "row_count": count,
                "file": f"data/powerbi/{table}.csv",
            }
            for table, count in export_counts.items()
        },
    }
    write_json(output_dir / "powerbi_export_manifest.json", powerbi_manifest)

    summary = {
        "status": "PASS",
        "source_rows": profile["source"]["original_row_count"],
        "staging_rows": cleaning["cleaned_staging_row_count"],
        "fact_rows": database_manifest["table_row_counts"]["fact_sales"],
        "duckdb_validation_checks": len(validation),
        "baseline_checks": len(baseline),
        "analysis_queries": analysis_manifest["queries_executed"],
        "powerbi_tables_exported": len(export_counts),
    }
    write_json(output_dir / "pipeline_run_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and validate the local retail analytics project."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    summary = build(args.root.resolve())
    print(
        "PASS: "
        f"{summary['source_rows']:,} source rows -> "
        f"{summary['staging_rows']:,} staging rows -> "
        f"{summary['fact_rows']:,} fact rows; "
        f"{summary['duckdb_validation_checks']} model checks and "
        f"{summary['baseline_checks']} baseline checks passed."
    )


if __name__ == "__main__":
    main()
