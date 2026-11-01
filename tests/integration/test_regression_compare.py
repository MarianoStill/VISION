import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "regression_compare.py"
spec = importlib.util.spec_from_file_location("regression_compare", SCRIPT)
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


def _xml(path, cases):
    body = ""
    for name, outcome, msg in cases:
        inner = {
            "pass": "",
            "fail": f'<failure type="AssertionError" message="{msg}"/>',
            "skip": '<skipped message="s"/>',
        }[outcome]
        body += f'<testcase classname="t" name="{name}">{inner}</testcase>'
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
    return str(path)


def test_identical_runs_are_ok(tmp_path):
    cases = [("a", "pass", ""), ("b", "skip", ""), ("c", "fail", "boom 1")]
    base = _xml(tmp_path / "b.xml", cases)
    cand = _xml(tmp_path / "c.xml", cases)
    assert rc.main([base, cand]) == 0


def test_pass_to_fail_is_regression(tmp_path):
    base = _xml(tmp_path / "b.xml", [("a", "pass", "")])
    cand = _xml(tmp_path / "c.xml", [("a", "fail", "x")])
    assert rc.main([base, cand]) == 1


def test_fixed_and_new_tests_are_not_regressions(tmp_path):
    base = _xml(tmp_path / "b.xml", [("a", "fail", "x")])
    cand = _xml(tmp_path / "c.xml", [("a", "pass", ""), ("n", "pass", "")])
    report = rc.compare(rc.load(base), rc.load(cand))
    assert report["fixed"] == ["t::a"] and report["new_pass"] == ["t::n"]
    assert not report["failed"]


def test_changed_failure_signature_fails_but_numbers_are_normalized(tmp_path):
    base = _xml(tmp_path / "b.xml", [("a", "fail", "got 1"), ("b", "fail", "got 1")])
    cand = _xml(tmp_path / "c.xml", [("a", "fail", "got 2"), ("b", "fail", "other")])
    report = rc.compare(rc.load(base), rc.load(cand))
    assert report["still_failing_same"] == ["t::a"]
    assert report["still_failing_changed"] == ["t::b"]
    assert report["failed"]


def test_removed_or_skipped_passing_test_fails(tmp_path):
    base = _xml(tmp_path / "b.xml", [("a", "pass", ""), ("b", "pass", "")])
    cand = _xml(tmp_path / "c.xml", [("a", "skip", "")])
    report = rc.compare(rc.load(base), rc.load(cand))
    assert report["pass_to_skip"] == ["t::a"]
    assert report["removed"] == ["t::b (PASS)"]
    assert report["failed"]
