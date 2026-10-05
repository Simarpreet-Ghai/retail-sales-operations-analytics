from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.ingest import write_json


MODEL_TABLES = ["staging_clean", "dim_date", "dim_customer", "dim_product", "dim_location", "fact_sales"]


def connect_database(path: Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def build_database(
    database_path: Path,
    schema_path: Path,
    cleaned: pd.DataFrame,
    model_tables: dict[str, pd.DataFrame],
    cleaning_summary: dict,
) -> dict:
    if database_path.exists():
        database_path.unlink()

    connection = connect_database(database_path)
    try:
        connection.execute(schema_path.read_text(encoding="utf-8"))

        audit = pd.DataFrame(
            [
                {"metric": key, "metric_value": str(cleaning_summary[key])}
                for key in [
                    "starting_row_count",
                    "duplicate_rows_removed",
                    "cleaned_staging_row_count",
                    "analytical_sales_row_count",
                ]
            ]
        )
        connection.register("_pipeline_audit_df", audit)
        connection.execute("INSERT INTO pipeline_audit SELECT * FROM _pipeline_audit_df")
        connection.unregister("_pipeline_audit_df")

        frames = {"staging_clean": cleaned, **model_tables}
        for table_name in MODEL_TABLES:
            view_name = f"_{table_name}_df"
            connection.register(view_name, frames[table_name])
            connection.execute(f"INSERT INTO {table_name} SELECT * FROM {view_name}")
            connection.unregister(view_name)

        connection.execute("CHECKPOINT")
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in MODEL_TABLES
        }
        return {
            "engine": f"DuckDB {duckdb.__version__}",
            "database_file": "data/analytics/retail_analytics.duckdb",
            "table_row_counts": counts,
            "database_size_bytes": database_path.stat().st_size,
        }
    finally:
        connection.close()


def run_validation(
    database_path: Path, validation_sql: Path, output_dir: Path
) -> pd.DataFrame:
    connection = connect_database(database_path, read_only=True)
    try:
        result = connection.execute(validation_sql.read_text(encoding="utf-8")).df()
    finally:
        connection.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_dir / "duckdb_validation_results.csv", index=False)
    failed = result.loc[result["status"].ne("PASS")]
    write_json(
        output_dir / "duckdb_validation_summary.json",
        {
            "engine": f"DuckDB {duckdb.__version__}",
            "checks_executed": int(len(result)),
            "checks_passed": int(result["status"].eq("PASS").sum()),
            "checks_failed": int(len(failed)),
            "status": "PASS" if failed.empty else "FAIL",
        },
    )
    if not failed.empty:
        raise RuntimeError(
            "DuckDB validation failed:\n" + failed.to_string(index=False)
        )
    return result


def run_analysis(
    database_path: Path, analysis_dir: Path, output_dir: Path
) -> tuple[dict[str, pd.DataFrame], dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = connect_database(database_path, read_only=True)
    results: dict[str, pd.DataFrame] = {}
    try:
        for path in sorted(analysis_dir.glob("*.sql")):
            result = connection.execute(path.read_text(encoding="utf-8")).df()
            results[path.stem] = result
            result.to_csv(output_dir / f"duckdb_{path.stem}.csv", index=False)
    finally:
        connection.close()

    manifest = {
        "engine": f"DuckDB {duckdb.__version__}",
        "database_file": "data/analytics/retail_analytics.duckdb",
        "queries_executed": len(results),
        "queries": {
            name: {
                "row_count": int(len(frame)),
                "output": f"outputs/duckdb_{name}.csv",
            }
            for name, frame in results.items()
        },
    }
    write_json(output_dir / "duckdb_analysis_manifest.json", manifest)
    return results, manifest


def export_powerbi_tables(database_path: Path, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = connect_database(database_path, read_only=True)
    counts: dict[str, int] = {}
    try:
        for table in ["fact_sales", "dim_date", "dim_customer", "dim_product", "dim_location"]:
            path = (output_dir / f"{table}.csv").resolve()
            sql_path = str(path).replace("'", "''")
            connection.execute(
                f"COPY (SELECT * FROM {table}) TO '{sql_path}' (HEADER, DELIMITER ',')"
            )
            counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()
    return counts
