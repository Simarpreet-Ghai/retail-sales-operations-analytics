from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import export_powerbi_tables
from src.ingest import write_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the five star-schema tables as Power BI-ready CSV files."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    counts = export_powerbi_tables(
        root / "data/analytics/retail_analytics.duckdb",
        root / "data/powerbi",
    )
    manifest = {
        "status": "CSV_EXPORT_COMPLETE",
        "power_bi_desktop_status": "NOT_EXECUTED",
        "tables": {
            table: {
                "row_count": count,
                "file": f"data/powerbi/{table}.csv",
            }
            for table, count in counts.items()
        },
    }
    write_json(root / "outputs/powerbi_export_manifest.json", manifest)
    print(f"PASS: exported {len(counts)} model tables to data/powerbi/.")


if __name__ == "__main__":
    main()
