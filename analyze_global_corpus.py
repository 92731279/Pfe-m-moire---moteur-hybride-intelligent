"""Run KPI analysis on data/samples/mt103_global_test_corpus.txt."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path
from statistics import mean

from src.pipeline import run_pipeline

CASE_HEADER_PATTERN = re.compile(r"^===\s*CASE\s+(\d+)\s*===\s*$", re.IGNORECASE)


def parse_global_corpus(corpus_text: str) -> list[dict]:
    cases: list[dict] = []
    case_id: str | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal case_id, lines
        if not case_id:
            return
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return
        cases.append({"case_id": case_id, "raw_message": "\n".join(lines)})

    for raw_line in corpus_text.splitlines():
        m = CASE_HEADER_PATTERN.match(raw_line.strip())
        if m:
            flush()
            case_id = m.group(1).zfill(3)
            lines = []
            continue
        if case_id:
            lines.append(raw_line.rstrip("\n"))

    flush()
    return cases


def evaluate_cases(cases: list[dict]) -> tuple[list[dict], dict]:
    per_case: list[dict] = []
    warning_counter: Counter[str] = Counter()

    for item in cases:
        case_id = item["case_id"]
        raw = item["raw_message"]
        result, _ = run_pipeline(raw, message_id=f"GLOBAL_{case_id}")

        warnings = [str(w) for w in (result.meta.warnings or [])]
        warning_counter.update(warnings)

        country = result.country_town.country if result.country_town else None
        town = result.country_town.town if result.country_town else None
        postal = result.country_town.postal_code if result.country_town else None

        per_case.append(
            {
                "case_id": case_id,
                "field_type": result.field_type,
                "rejected": bool(result.meta.rejected),
                "fallback_used": bool(result.meta.fallback_used),
                "confidence": float(result.meta.parse_confidence or 0.0),
                "country": country,
                "town": town,
                "postal_code": postal,
                "warning_count": len(warnings),
                "warnings": " | ".join(warnings),
            }
        )

    total = len(per_case)
    rejected = sum(1 for row in per_case if row["rejected"])
    fallback = sum(1 for row in per_case if row["fallback_used"])
    with_country = sum(1 for row in per_case if row["country"])
    with_town = sum(1 for row in per_case if row["town"])
    with_postal = sum(1 for row in per_case if row["postal_code"])

    summary = {
        "total_cases": total,
        "accepted_cases": total - rejected,
        "rejected_cases": rejected,
        "acceptance_rate": (total - rejected) / total if total else 0.0,
        "fallback_cases": fallback,
        "fallback_rate": fallback / total if total else 0.0,
        "avg_confidence": mean([row["confidence"] for row in per_case]) if total else 0.0,
        "country_coverage": with_country / total if total else 0.0,
        "town_coverage": with_town / total if total else 0.0,
        "postal_coverage": with_postal / total if total else 0.0,
        "top_warnings": warning_counter.most_common(12),
    }

    return per_case, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(summary: dict) -> None:
    print("=== GLOBAL CORPUS KPI ===")
    print(f"Total cases         : {summary['total_cases']}")
    print(f"Accepted            : {summary['accepted_cases']}")
    print(f"Rejected            : {summary['rejected_cases']}")
    print(f"Acceptance rate     : {summary['acceptance_rate']:.2%}")
    print(f"Fallback rate       : {summary['fallback_rate']:.2%}")
    print(f"Avg confidence      : {summary['avg_confidence']:.3f}")
    print(f"Country coverage    : {summary['country_coverage']:.2%}")
    print(f"Town coverage       : {summary['town_coverage']:.2%}")
    print(f"Postal coverage     : {summary['postal_coverage']:.2%}")
    print("Top warnings:")
    for warning, count in summary["top_warnings"]:
        print(f"  - {warning}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze global MT103 corpus KPIs.")
    parser.add_argument(
        "--input",
        default="data/samples/mt103_global_test_corpus.txt",
        help="Path to the corpus text file",
    )
    parser.add_argument(
        "--csv",
        default="data/outputs/global_corpus_results.csv",
        help="Output CSV path for per-case results",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    csv_path = Path(args.csv)

    if not input_path.exists():
        raise FileNotFoundError(f"Corpus file not found: {input_path}")

    corpus_text = input_path.read_text(encoding="utf-8")
    cases = parse_global_corpus(corpus_text)
    per_case, summary = evaluate_cases(cases)
    write_csv(csv_path, per_case)
    print_summary(summary)
    print(f"CSV report saved to: {csv_path}")


if __name__ == "__main__":
    main()
