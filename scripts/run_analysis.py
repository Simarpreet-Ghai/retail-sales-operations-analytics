from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import save_business_outputs
from src.database import run_analysis, run_validation
from src.validate import reconcile_verified_baseline


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-run DuckDB validations, analytical SQL, and baseline reconciliation."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = root / "outputs"
    database_path = root / "data/analytics/retail_analytics.duckdb"

    validation = run_validation(
        database_path,
        root / "sql/validation/model_checks.sql",
        output_dir,
    )
    results, manifest = run_analysis(
        database_path,
        root / "sql/analysis",
        output_dir,
    )
    save_business_outputs(output_dir, results)
    baseline = reconcile_verified_baseline(
        load_json(output_dir / "raw_profile.json"),
        load_json(output_dir / "cleaning_summary.json"),
        load_json(output_dir / "duckdb_database_manifest.json"),
        results,
        output_dir,
    )
    print(
        f"PASS: {len(validation)} validations, "
        f"{manifest['queries_executed']} analyses, and "
        f"{len(baseline)} baseline checks completed."
    )


if __name__ == "__main__":
    main()
