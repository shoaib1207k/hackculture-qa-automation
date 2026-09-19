"""Command line: score a lead and show the decision, then each check with its timestamp.

    uv run python -m hackathon_qa_automation.cli score 3613790
    uv run python -m hackathon_qa_automation.cli score 3613791 --json
"""

import argparse
import asyncio
import os

from .common.logging_config import setup_logging
from .pipeline import LeadScore, score_lead

_MARK = {"pass": "PASS", "fail": "FAIL", "uncertain": "????"}


def _mmss(seconds: float | None) -> str:
    return "--:--" if seconds is None else f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def render(score: LeadScore) -> str:
    lines = [f"Lead {score.lead_id} | {score.retailer_id} | checklist {score.checklist_version} "
             f"| call {score.call_date}",
             f"DECISION: {score.decision}"]
    lines += [f"  - {r}" for r in score.reasons]
    if score.error:
        lines.append(f"  ! error: {score.error}")
    for v in score.verdicts:
        crit = "critical" if v.critical else "note"
        span = ("no timestamp" if v.timestamp_start is None
                else f"{_mmss(v.timestamp_start)}-{_mmss(v.timestamp_end)}")
        lines.append(f"\n{_MARK[v.verdict]}  [{v.check_type}] {v.check_id} ({crit}, "
                     f"conf {v.confidence:.2f})  {span}  {v.evidence_segment_ids}")
        lines.append(f"      {v.reasoning}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(prog="hackathon-qa-automation")
    sub = parser.add_subparsers(dest="command", required=True)
    score_cmd = sub.add_parser("score", help="score one lead")
    score_cmd.add_argument("lead_id")
    score_cmd.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args()

    setup_logging(os.environ.get("LOG_LEVEL", "WARNING"))  # keep the report readable
    score = asyncio.run(score_lead(args.lead_id))
    print(score.model_dump_json(indent=2) if args.json else render(score))


if __name__ == "__main__":
    main()
