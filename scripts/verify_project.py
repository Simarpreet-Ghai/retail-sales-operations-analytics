from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingest import write_json


EXPECTED_SOURCE_SHA256 = (
    "bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980"
)
TEXT_SUFFIXES = {".md", ".py", ".sql", ".txt", ".toml", ".yaml", ".yml"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def has_legacy_platform_reference(root: Path) -> bool:
    legacy_tokens = [("snow" + "flake").lower(), ("sql" + "ite").lower()]
    ignored_parts = {".git", ".venv", "__pycache__"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        if any(token in content for token in legacy_tokens):
            return True
    return False


def verify(root: Path) -> dict:
    outputs = root / "outputs"
    profile = load_json(outputs / "raw_profile.json")
    cleaning = load_json(outputs / "cleaning_summary.json")
    database = load_json(outputs / "duckdb_database_manifest.json")
    validation = load_json(outputs / "duckdb_validation_summary.json")
    analysis = load_json(outputs / "duckdb_analysis_manifest.json")
    baseline = load_json(outputs / "baseline_reconciliation.json")
    powerbi = load_json(outputs / "powerbi_export_manifest.json")

    checks: dict[str, bool] = {
        "source_workbook_hash_matches": sha256(root / "data/raw/online_retail_II.xlsx")
        == EXPECTED_SOURCE_SHA256,
        "raw_to_staging_rows_reconcile": profile["source"]["original_row_count"]
        == cleaning["cleaned_staging_row_count"] + cleaning["duplicate_rows_removed"],
        "staging_to_fact_rows_reconcile": cleaning["analytical_sales_row_count"]
        == database["table_row_counts"]["fact_sales"],
        "all_database_checks_pass": validation["status"] == "PASS"
        and validation["checks_failed"] == 0,
        "all_baseline_checks_pass": baseline["status"] == "PASS"
        and baseline["checks_failed"] == 0,
        "all_analysis_queries_executed": analysis["queries_executed"] == 8,
        "all_powerbi_tables_exported": len(powerbi["tables"]) == 5
        and all(
            item["row_count"] == database["table_row_counts"][table]
            and (root / item["file"]).exists()
            for table, item in powerbi["tables"].items()
        ),
        "generated_database_exists": (root / database["database_file"]).exists(),
        "no_private_key_files": not any(
            path.is_file() and path.suffix.lower() in {".pem", ".p8", ".key"}
            for path in root.rglob("*")
            if ".venv" not in path.parts
        ),
        "no_legacy_platform_references": not has_legacy_platform_reference(root),
        "dashboard_not_claimed_complete": not (root / "images/dashboard.png").exists(),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks_executed": len(checks),
        "checks_passed": sum(checks.values()),
        "checks_failed": len(checks) - sum(checks.values()),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }


def save_report(output_dir: Path, report: dict) -> None:
    write_json(output_dir / "integrity_report.json", report)
    lines = ["# Project integrity report", "", f"Overall status: **{report['status']}**", ""]
    for name, passed in report["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'}: `{name}`")
    (output_dir / "integrity_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile the generated local project artifacts."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    report = verify(root)
    save_report(root / "outputs", report)
    print(
        f"Project integrity: {report['status']} "
        f"({report['checks_passed']}/{report['checks_executed']} checks passed)."
    )
    if report["failed_checks"]:
        raise SystemExit(f"Failed checks: {', '.join(report['failed_checks'])}")


if __name__ == "__main__":
    main()
