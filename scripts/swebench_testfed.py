#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maref-org
# SPDX-License-Identifier: Apache-2.0
"""Run one SWE-bench Lite instance with test feedback between agent rounds.

The point of this harness is the loop, not the score: setup once, then for each
rep let the agent edit, run the target tests *in the same working tree*, and if
the tests still fail hand the tail of that output back to the agent for another
round. Every round's cost, test counts and wall time are recorded, so
"how many attempts did the fix take and what did it cost" becomes measurable
instead of a single pass/fail bit.

Three properties matter and are enforced rather than assumed:

* **The bug is really reproduced.** Setup applies ``test_patch`` and fails hard
  unless the target tests fail. Without that check a missing/broken test patch
  makes every rep "pass" without any fix — a false positive that costs real
  money to collect.
* **Editing the tests is not a fix.** Any changed path under the test directory
  ends the rep as ``tampered`` before the tests run.
* **Unknown cost is not zero.** See :func:`mas_eval.runner.testfed.summarize_rounds`.

Usage:
    python scripts/swebench_testfed.py \
      --dataset /path/to/lite-astropy.json \
      --instance astropy__astropy-14365 \
      --setup-dir /path/to/testfed --output /path/to/results.jsonl
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_AGENT = (
    "claude -p --bare --permission-mode acceptEdits "
    "--max-budget-usd 1.50 --output-format json"
)

# Extra runtime deps for building astropy 5.x in place and running its test
# suite. Pins that are not obvious:
#   setuptools==58.0.4 — later versions fail astropy's setup.py
#   pytest<8           — pytest 8 rewraps failures as DID NOT WARN, so the
#                        traceback no longer matches the official evaluator
#   numpy<2            — astropy 5.2 predates the numpy 2 ABI
SETUP_DEPS = (
    "numpy<2",
    "setuptools==58.0.4",
    "wheel",
    "Cython<3",
    "jinja2",
    "pyerfa>=2.0",
    "hypothesis",
    "pytest<8",
    "pytest-doctestplus",
    "pytest-astropy-header",
    "pytest-astropy",
    "PyYAML",
    "extension-helpers",
    "setuptools_scm",
)

# The target tests take ~0.2s on this instance; the timeout only exists so a
# broken edit cannot hang the run forever.
TEST_TIMEOUT_SECONDS = 600
# Characters of the final test output kept in the result row.
ROW_TAIL_CHARS = 2000


def _log(message: str) -> None:
    print(message, flush=True)


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing output as text (never raising on exit code)."""
    return subprocess.run(
        cmd,
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _check(proc: subprocess.CompletedProcess[str], what: str) -> None:
    """Abort with the tail of the output when ``proc`` failed."""
    if proc.returncode == 0:
        return
    detail = ((proc.stdout or "") + (proc.stderr or ""))[-1500:]
    raise SystemExit(f"{what} failed (exit {proc.returncode}):\n{detail}")


def _parse_env(pairs: list[str] | None) -> dict[str, str]:
    """Turn repeated ``KEY=VALUE`` flags into a dict for the child process."""
    env: dict[str, str] = {}
    for raw in pairs or []:
        key, sep, value = raw.partition("=")
        if not sep or not key:
            raise SystemExit(f"--env expects KEY=VALUE, got {raw!r}")
        env[key] = value
    return env


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / "bin" / "python"


def ensure_venv(venv_dir: Path, python_exe: str) -> Path:
    """Create (or reuse) the build/test venv and install the pinned deps."""
    py = _venv_python(venv_dir)
    if py.exists():
        _log(f"[setup] reusing venv {venv_dir}")
        return py

    started = time.time()
    _log(f"[setup] creating venv {venv_dir} from {python_exe} ...")
    _check(_run([python_exe, "-m", "venv", str(venv_dir)], timeout=600), "venv")

    probe = _run(
        [str(py), "-c", "import sys; print('%d %d' % sys.version_info[:2])"],
        timeout=60,
    )
    _check(probe, "venv python probe")
    major, minor = (int(part) for part in probe.stdout.split())
    _log(f"[setup] venv python {major}.{minor}")
    if (major, minor) >= (3, 12):
        # Failing here saves ~4 minutes of pip before setup.py rejects it.
        raise SystemExit(
            f"venv python {major}.{minor} cannot build this instance; "
            "pass --python python3.11 (or 3.9/3.10)"
        )

    _log(f"[setup] pip install {len(SETUP_DEPS)} deps ...")
    _check(
        _run(
            [
                str(py),
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                *SETUP_DEPS,
            ],
            timeout=2400,
        ),
        "pip install",
    )
    _log(f"[setup] venv ready in {time.time() - started:.0f}s")
    return py


def build_ext(py: Path, base_dir: Path) -> float:
    """Build the C extensions in place; returns elapsed seconds."""
    started = time.time()
    _log("[setup] build_ext --inplace ...")
    _check(
        _run(
            [str(py), "setup.py", "build_ext", "--inplace"], cwd=base_dir, timeout=1800
        ),
        "build_ext",
    )
    elapsed = time.time() - started
    n_so = len(list(base_dir.rglob("*.so")))
    _log(f"[setup] built {n_so} .so in {elapsed:.0f}s")
    return elapsed


def apply_test_patch(base_dir: Path, patch_text: str, scratch: Path) -> str:
    """Apply the instance's test patch; returns which mechanism worked.

    ``git apply`` is tried first, then ``patch -p1``. A patch that is already
    applied is recognised so ``--skip-setup`` re-runs stay idempotent.
    """
    scratch.write_text(patch_text, encoding="utf-8")

    if _run(["git", "apply", "--check", str(scratch)], cwd=base_dir).returncode == 0:
        _check(
            _run(
                ["git", "apply", "--whitespace=nowarn", str(scratch)],
                cwd=base_dir,
            ),
            "git apply test_patch",
        )
        return "git apply"

    reverse = _run(["git", "apply", "--reverse", "--check", str(scratch)], cwd=base_dir)
    if reverse.returncode == 0:
        return "already applied"

    patched = _run(
        ["patch", "-p1", "--batch", "--forward", "-i", str(scratch)],
        cwd=base_dir,
    )
    if patched.returncode == 0:
        return "patch -p1"
    raise SystemExit(
        "test_patch could not be applied:\n"
        + ((patched.stdout or "") + (patched.stderr or ""))[-1500:]
    )


def commit_base(base_dir: Path) -> None:
    """Commit setup edits so each rep starts from a clean working tree.

    Without this the test patch itself would show up in every rep's
    ``git diff``, inflating ``patch_bytes`` and looking like tampering.
    """
    status = _run(["git", "status", "--porcelain"], cwd=base_dir)
    if not status.stdout.strip():
        return
    _check(_run(["git", "add", "-A"], cwd=base_dir), "git add")
    _check(
        _run(
            [
                "git",
                "-c",
                "user.email=testfed@local",
                "-c",
                "user.name=testfed",
                "commit",
                "-q",
                "-m",
                "testfed: apply test_patch (baseline snapshot)",
            ],
            cwd=base_dir,
        ),
        "git commit baseline",
    )
    _log("[setup] committed test_patch into the base snapshot")


def run_target_tests(
    repo_dir: Path, py: Path, test_ids: list[str]
) -> tuple[int, int, str]:
    """Run the instance's FAIL_TO_PASS tests; returns (passed, failed, output).

    ``-p no:cacheprovider`` keeps ``.pytest_cache`` out of the tree so the
    agent's diff (and the tampering check) sees only real changes.
    """
    cmd = [str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider", *test_ids]
    try:
        proc = _run(cmd, cwd=repo_dir, timeout=TEST_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return 0, 1, f"pytest timed out after {TEST_TIMEOUT_SECONDS}s"

    from mas_eval.oracle.swe_bench import _count

    output = (proc.stdout or "") + (proc.stderr or "")
    passed = _count(output, "passed")
    failed = _count(output, "failed")
    errors = _count(output, "error")
    if passed == 0 and failed == 0 and errors == 0:
        # pytest died before summarising (import error, crash): count as failed
        failed = 1 if proc.returncode != 0 else 0
    return passed, failed + errors, output


def changed_files(repo_dir: Path) -> list[str]:
    """Repo-relative paths the agent changed (tracked + new files)."""
    _run(["git", "add", "-N", "."], cwd=repo_dir)
    proc = _run(["git", "diff", "--name-only"], cwd=repo_dir)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def derive_test_prefix(test_ids: list[str], fallback: str) -> str:
    """Test directory of the target tests (``dir/of/test.py`` -> ``dir/of/``)."""
    for test_id in test_ids:
        path = test_id.split("::")[0]
        parent = Path(path).parent
        if str(parent) not in ("", "."):
            return str(parent).rstrip("/") + "/"
    return fallback


def fresh_rep_dir(setup_dir: Path, index: int) -> Path:
    """First unused ``rep-<index>`` directory — never deletes an existing one."""
    candidate = setup_dir / f"rep-{index}"
    suffix = 1
    while candidate.exists():
        candidate = setup_dir / f"rep-{index}-{suffix}"
        suffix += 1
    return candidate


def run_rep(
    *,
    rep_index: int,
    base_dir: Path,
    setup_dir: Path,
    py: Path,
    runner: Any,
    task: dict,
    test_ids: list[str],
    test_prefix: str,
    max_rounds: int,
    feedback_chars: int,
) -> dict:
    """Run one rep: copy snapshot, then up to ``max_rounds`` agent+test rounds."""
    from mas_eval.runner.prompt import build_prompt
    from mas_eval.runner.testfed import (
        build_feedback_prompt,
        detect_test_tampering,
        summarize_rounds,
    )

    instance_id = task["task_id"]
    problem = task["problem_statement"]

    rep_dir = fresh_rep_dir(setup_dir, rep_index)
    copy_started = time.time()
    _log(f"[rep {rep_index}] copying {base_dir} -> {rep_dir.name} ...")
    shutil.copytree(base_dir, rep_dir, symlinks=True)
    _log(f"[rep {rep_index}] snapshot ready in {time.time() - copy_started:.1f}s")

    rounds: list[dict] = []
    resolved = False
    tampered = False
    test_output = ""

    for round_no in range(1, max_rounds + 1):
        if round_no == 1:
            prompt = build_prompt(problem)
        else:
            prompt = build_feedback_prompt(problem, test_output, feedback_chars)
            appended = len(prompt) - len(build_prompt(problem))
            preview = test_output[-feedback_chars:].strip()[:120].replace("\n", " | ")
            _log(
                f"[rep {rep_index}] round {round_no}: feedback={appended}B "
                f"carried_from_round_{round_no - 1}={preview!r}"
            )

        result = runner.run(prompt, rep_dir, instance_id)
        usage = result.usage
        outcome = (usage or {}).get("outcome", "unknown")
        cost = (usage or {}).get("total_cost_usd")
        _log(
            f"[rep {rep_index}] round {round_no}: agent exit="
            f"{result.record.exit_code} {result.duration_s}s "
            f"patch={len(result.patch)}B cost={cost} outcome={outcome}"
        )

        changed = changed_files(rep_dir)
        tampered = detect_test_tampering(changed, test_prefix)
        if tampered:
            rounds.append(
                {
                    "round": round_no,
                    "usage": usage,
                    "test_passed": 0,
                    "test_failed": 0,
                    "patch_bytes": len(result.patch),
                    "wall_s": result.duration_s,
                }
            )
            _log(
                f"[rep {rep_index}] round {round_no}: TAMPERED — agent edited "
                f"test files: {[c for c in changed if c.startswith(test_prefix)]}"
            )
            break

        test_started = time.time()
        passed, failed, test_output = run_target_tests(rep_dir, py, test_ids)
        wall = round(result.duration_s + (time.time() - test_started), 2)
        rounds.append(
            {
                "round": round_no,
                "usage": usage,
                "test_passed": passed,
                "test_failed": failed,
                "patch_bytes": len(result.patch),
                "wall_s": wall,
            }
        )
        _log(
            f"[rep {rep_index}] round {round_no}: tests passed={passed} "
            f"failed={failed} changed={len(changed)} files {wall}s"
        )

        if failed == 0 and passed > 0:
            resolved = True
            break

    summary = summarize_rounds(rounds)
    return {
        "instance_id": instance_id,
        "rep": rep_index,
        "resolved": resolved,
        "rounds_used": summary["rounds_used"],
        "tampered": tampered,
        "rounds": rounds,
        "total_cost_usd": summary["total_cost_usd"],
        "cost_measurable": summary["cost_measurable"],
        "outcome": summary["outcome"],
        "test_output_tail": test_output[-ROW_TAIL_CHARS:],
        "error": "",
    }


def _print_summary(rows: list[dict], output_path: Path) -> None:
    runs = len(rows)
    resolved = sum(1 for row in rows if row["resolved"])
    tampered = sum(1 for row in rows if row["tampered"])
    histogram = Counter(row["rounds_used"] for row in rows)
    measurable = [row for row in rows if row["cost_measurable"]]
    unmeasurable = runs - len(measurable)
    # Fail-closed: rows with unknown cost contribute nothing to the sum, and
    # the summary says so instead of pretending the total is complete.
    total_cost = sum(row["total_cost_usd"] or 0.0 for row in measurable)

    print("\n=== summary ===")
    print(f"runs:              {runs}")
    print(f"resolved:          {resolved}/{runs}")
    print(
        "rounds_used:       "
        + " ".join(f"{k}={v}" for k, v in sorted(histogram.items()))
    )
    print(f"tampered:          {tampered}")
    suffix = "" if not unmeasurable else f" ({unmeasurable} unknown, NOT zero)"
    print(f"total_cost:        {total_cost:.4f}{suffix}")
    if unmeasurable:
        print("cost_per_resolved: unknown (unmeasurable runs)")
    elif resolved:
        print(f"cost_per_resolved: {total_cost / resolved:.4f}")
    else:
        print("cost_per_resolved: n/a (0 resolved)")
    print(f"results:           {output_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SWE-bench instance with test feedback between agent rounds"
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument(
        "--reps", type=int, default=3, help="Independent reps (fresh snapshot each)"
    )
    parser.add_argument(
        "--rounds", type=int, default=3, help="Max agent rounds per rep"
    )
    parser.add_argument(
        "--setup-dir",
        required=True,
        help="Holds the base snapshot and the shared venv (reused across runs)",
    )
    parser.add_argument("--venv", help="Existing venv (default: <setup-dir>/venv)")
    parser.add_argument(
        "--python",
        default="python3",
        help="Interpreter used to create the venv when it is missing",
    )
    parser.add_argument("--agent-cmd", default=DEFAULT_AGENT)
    parser.add_argument(
        "--env",
        action="append",
        metavar="KEY=VALUE",
        help="Environment variable for the agent process (repeatable)",
    )
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Reuse the existing base snapshot (clone/build/test_patch already done)",
    )
    parser.add_argument(
        "--feedback-chars",
        type=int,
        default=2000,
        help="Tail characters of the test output fed back to the agent",
    )
    args = parser.parse_args(argv)

    if args.reps < 1 or args.rounds < 1:
        raise SystemExit("--reps and --rounds must be >= 1")

    from mas_eval.oracle.swe_bench import load_lite_tasks
    from mas_eval.runner.local_cli import LocalCLIRunner
    from mas_eval.runner.repo import prepare_repo
    from mas_eval.runner.testfed import DEFAULT_TEST_PREFIX
    from mas_eval.runner.usage import parse_claude_usage

    tasks = [t for t in load_lite_tasks(args.dataset) if t["task_id"] == args.instance]
    if not tasks:
        raise SystemExit(f"instance {args.instance!r} not found in {args.dataset}")
    task = tasks[0]
    test_ids = list(task["FAIL_TO_PASS"])
    if not test_ids:
        raise SystemExit(f"instance {args.instance!r} has no FAIL_TO_PASS tests")
    test_prefix = derive_test_prefix(test_ids, DEFAULT_TEST_PREFIX)
    if not test_prefix:
        print(
            f"WARNING: could not derive test prefix from FAIL_TO_PASS={test_ids}; "
            f"tampering detection will be disabled",
            file=sys.stderr,
        )

    setup_dir = Path(args.setup_dir).expanduser().resolve()
    setup_dir.mkdir(parents=True, exist_ok=True)
    base_dir = setup_dir / "base"
    venv_dir = Path(args.venv).expanduser() if args.venv else setup_dir / "venv"

    _log(f"instance:    {args.instance}")
    _log(f"tests:       {test_ids}")
    _log(f"test prefix: {test_prefix}")
    _log(
        f"runner:      reps={args.reps} rounds={args.rounds} "
        f"timeout={args.timeout}s feedback_chars={args.feedback_chars}"
    )
    _log(f"agent:       {args.agent_cmd}")

    setup_started = time.time()

    # ---- setup (once per setup-dir) -------------------------------------
    t0 = time.time()
    if args.skip_setup:
        if not (base_dir / ".git").exists():
            raise SystemExit(f"--skip-setup needs an existing snapshot at {base_dir}")
        _log(f"[setup] reusing snapshot {base_dir}")
    else:
        if (base_dir / ".git").exists():
            _log(f"[setup] reusing existing clone {base_dir} (re-syncing base_commit)")
        else:
            _log(f"[setup] cloning {task['repo']} @ {task['base_commit'][:12]} ...")
        prepare_repo(task["repo"], task["base_commit"], base_dir)
    clone_s = time.time() - t0

    py = ensure_venv(venv_dir, args.python)

    t0 = time.time()
    if args.skip_setup:
        _log("[setup] skipping build_ext --inplace (snapshot reused)")
        build_s = 0.0
    else:
        build_s = build_ext(py, base_dir)

    t0 = time.time()
    scratch = setup_dir / "test_patch.diff"
    mechanism = apply_test_patch(base_dir, task["test_patch"], scratch)
    _log(f"[setup] test_patch: {mechanism} ({time.time() - t0:.1f}s)")
    if mechanism != "already applied":
        commit_base(base_dir)
    else:
        _log("[setup] test_patch already applied; leaving the commit as is")

    t0 = time.time()
    passed, failed, setup_output = run_target_tests(base_dir, py, test_ids)
    _log(
        f"[setup] self-check: passed={passed} failed={failed} ({time.time() - t0:.1f}s)"
    )
    if failed == 0:
        raise SystemExit(
            "self-check FAILED: the target tests pass on the untouched base "
            "snapshot, so the bug is not reproduced (missing test_patch?). "
            "Every rep would look resolved without a fix — refusing to run.\n"
            f"self-check output tail:\n{setup_output[-800:]}"
        )
    _log("[setup] self-check ok: bug reproduced (target tests fail as expected)")
    _log(
        f"[setup] total {time.time() - setup_started:.0f}s "
        f"(clone {clone_s:.0f}s + build {build_s:.0f}s + venv/patch/check)"
    )

    # ---- reps ------------------------------------------------------------
    child_env = _parse_env(args.env)
    usage_parser = parse_claude_usage if "claude" in args.agent_cmd else None
    runner = LocalCLIRunner(
        "local-cli-agent-testfed",
        shlex.split(args.agent_cmd),
        timeout_seconds=args.timeout,
        usage_parser=usage_parser,
        env=child_env or None,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")

    rows: list[dict] = []
    for rep_index in range(1, args.reps + 1):
        started = time.time()
        try:
            row = run_rep(
                rep_index=rep_index,
                base_dir=base_dir,
                setup_dir=setup_dir,
                py=py,
                runner=runner,
                task=task,
                test_ids=test_ids,
                test_prefix=test_prefix,
                max_rounds=args.rounds,
                feedback_chars=args.feedback_chars,
            )
        except Exception as exc:  # keep the remaining reps alive
            row = {
                "instance_id": args.instance,
                "rep": rep_index,
                "resolved": False,
                "rounds_used": 0,
                "tampered": False,
                "rounds": [],
                "total_cost_usd": None,
                "cost_measurable": False,
                "outcome": "error",
                "test_output_tail": "",
                "error": f"{type(exc).__name__}: {exc}",
            }
            _log(f"[rep {rep_index}] ERROR {row['error']}")

        row["wall_seconds"] = round(time.time() - started, 1)
        rows.append(row)
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        _log(
            f"[rep {rep_index}] done resolved={row['resolved']} "
            f"rounds={row['rounds_used']} tampered={row['tampered']} "
            f"cost={row['total_cost_usd']} {row['wall_seconds']}s"
        )

    _print_summary(rows, output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
