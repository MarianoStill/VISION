"""Differential comparison of two pytest JUnit XML reports (baseline vs candidate).

Usage: python scripts/regression_compare.py BASELINE.xml CANDIDATE.xml [--json OUT]

Exit code 1 when any test regresses (PASS->FAIL), a FAIL changes its failure
signature, a baseline PASS disappears, or the candidate has collection errors.
Only test ids, outcomes and normalized failure signatures are reported; no
messages or data values are written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def _signature(node) -> str:
    kind = node.get("type") or node.tag
    message = re.sub(r"0x[0-9a-fA-F]+|\d+", "N", node.get("message") or "")
    message = re.sub(r"[A-Za-z]:\\[^\s'\"]*|/[^\s'\"]*/[^\s'\"]*", "<path>", message)
    return hashlib.sha256(f"{kind}|{message[:300]}".encode()).hexdigest()[:12]


def load(path) -> dict:
    tests, errors = {}, []
    for case in ET.parse(path).getroot().iter("testcase"):
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if failure is not None or error is not None:
            node = failure if failure is not None else error
            tests[test_id] = (FAIL, _signature(node))
            if error is not None and not case.get("name"):
                errors.append(test_id)
        elif skipped is not None:
            tests[test_id] = (SKIP, None)
        else:
            tests[test_id] = (PASS, None)
    return {"tests": tests, "collection_errors": errors}


def compare(baseline: dict, candidate: dict) -> dict:
    base, cand = baseline["tests"], candidate["tests"]
    result = {
        "regressions": [], "fixed": [], "still_failing_same": [],
        "still_failing_changed": [], "new_pass": [], "new_fail": [],
        "new_skip": [], "removed": [], "skipped_to_pass": [], "pass_to_skip": [],
        "unchanged": 0, "collection_errors": candidate["collection_errors"],
    }
    for test_id, (outcome, sig) in sorted(cand.items()):
        if test_id not in base:
            key = {PASS: "new_pass", FAIL: "new_fail", SKIP: "new_skip"}[outcome]
            result[key].append(test_id)
            continue
        old, old_sig = base[test_id]
        if old == PASS and outcome == FAIL:
            result["regressions"].append(test_id)
        elif old == FAIL and outcome == PASS:
            result["fixed"].append(test_id)
        elif old == FAIL and outcome == FAIL:
            same = old_sig == sig
            result["still_failing_same" if same else "still_failing_changed"].append(test_id)
        elif old == SKIP and outcome == PASS:
            result["skipped_to_pass"].append(test_id)
        elif old == PASS and outcome == SKIP:
            result["pass_to_skip"].append(test_id)
        else:
            result["unchanged"] += 1
    for test_id, (outcome, _) in sorted(base.items()):
        if test_id not in cand:
            result["removed"].append(test_id + f" ({outcome})")
    result["failed"] = bool(
        result["regressions"] or result["still_failing_changed"]
        or result["collection_errors"] or result["pass_to_skip"]
        or any(item.endswith("(PASS)") for item in result["removed"])
    )
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args(argv)
    report = compare(load(args.baseline), load(args.candidate))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    for key, value in report.items():
        if key in ("failed", "unchanged"):
            continue
        if value:
            print(f"{key}: {len(value)}")
            for item in value[:50]:
                print(f"  - {item}")
    print(f"unchanged: {report['unchanged']}")
    print("RESULT: " + ("REGRESSION" if report["failed"] else "OK"))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
