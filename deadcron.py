#!/usr/bin/env python3
"""deadcron - find scheduled jobs that exited 0 but did nothing.

Reads a runs log (JSONL, one run per line) and, optionally, an effects log
(JSONL, one side effect per line, joined to a run by run_id). Reports every
run that finished "green" (exit code 0) but produced fewer side effects than
that job is expected to produce.

Exit codes: 0 every green run did work, 1 at least one green run did nothing,
2 input unreadable (never reported as clean).
Standard library only.
"""
import argparse, json, sys
from collections import defaultdict

VERSION = "0.1.0"


class Unreadable(Exception):
    pass


def load_jsonl(path, required):
    rows = []
    try:
        fh = open(path, encoding="utf-8")
    except OSError as e:
        raise Unreadable("%s: %s" % (path, e.strerror or e))
    with fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                raise Unreadable("%s line %d: not valid JSON" % (path, n))
            if not isinstance(row, dict):
                raise Unreadable("%s line %d: not a JSON object" % (path, n))
            missing = [k for k in required if k not in row]
            if missing:
                raise Unreadable("%s line %d: missing %s" % (path, n, ", ".join(missing)))
            rows.append(row)
    return rows


def load_expect(path):
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as e:
        raise Unreadable("%s: %s" % (path, e.strerror or e))
    except ValueError:
        raise Unreadable("%s: not valid JSON" % path)
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, dict):
        raise Unreadable("%s: expected an object with a 'jobs' map" % path)
    out = {}
    for job, spec in jobs.items():
        m = spec.get("min_effects") if isinstance(spec, dict) else None
        if not isinstance(m, int) or m < 0:
            raise Unreadable("%s: job %r needs an integer min_effects >= 0" % (path, job))
        out[job] = m
    return out


def effect_count(run, effects_by_run, have_effects_log):
    """Return (count, source). count is None when it genuinely cannot be known."""
    if have_effects_log:
        return len(effects_by_run.get(str(run["run_id"]), [])), "effects log"
    v = run.get("effects")
    if isinstance(v, bool) or v is None:
        return None, "no effects recorded"
    if isinstance(v, int) and v >= 0:
        return v, "run record"
    if isinstance(v, list):
        return len(v), "run record"
    return None, "unreadable 'effects' value"


def audit(runs, effects, expect, default_min):
    effects_by_run = defaultdict(list)
    for e in effects or []:
        effects_by_run[str(e["run_id"])].append(e)
    have_log = effects is not None
    rows, by_job = [], defaultdict(list)
    for r in runs:
        job = str(r["job"])
        need = expect.get(job, default_min)
        code = r["exit_code"]
        if not isinstance(code, int) or isinstance(code, bool):
            verdict, n, src = "UNKNOWN", None, "exit_code not an integer"
        elif code != 0:
            verdict, n, src = "FAILED_LOUD", None, "non-zero exit"
        else:
            n, src = effect_count(r, effects_by_run, have_log)
            if n is None:
                verdict = "UNKNOWN"
            elif n < need:
                verdict = "GREEN_EMPTY"
            else:
                verdict = "OK"
        row = {"job": job, "run_id": str(r["run_id"]), "at": str(r.get("started", "?")),
               "exit_code": code, "effects": n, "needed": need, "verdict": verdict, "source": src}
        rows.append(row)
        by_job[job].append(row)
    return rows, by_job


def streak(job_rows):
    """Consecutive GREEN_EMPTY runs at the end of the job's history (log order)."""
    s = 0
    for row in reversed(job_rows):
        if row["verdict"] == "GREEN_EMPTY":
            s += 1
        elif row["verdict"] == "OK":
            break
    return s


def main(argv=None):
    p = argparse.ArgumentParser(prog="deadcron", description=__doc__.splitlines()[0])
    p.add_argument("--runs", required=True, help="JSONL: job, run_id, exit_code [, started, effects]")
    p.add_argument("--effects", help="JSONL: run_id [, what] - one line per side effect")
    p.add_argument("--expect", help="JSON: {\"jobs\": {\"name\": {\"min_effects\": N}}}")
    p.add_argument("--default-min", type=int, default=1,
                   help="effects a green run must produce when --expect does not name the job (default 1)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--version", action="version", version=VERSION)
    a = p.parse_args(argv)
    try:
        runs = load_jsonl(a.runs, ["job", "run_id", "exit_code"])
        effects = load_jsonl(a.effects, ["run_id"]) if a.effects else None
        expect = load_expect(a.expect)
    except Unreadable as e:
        print("VERDICT UNKNOWN")
        print("input unreadable: %s" % e)
        print("Nothing was checked, so nothing is reported clean.")
        return 2
    rows, by_job = audit(runs, effects, expect, a.default_min)
    counts = defaultdict(int)
    for r in rows:
        counts[r["verdict"]] += 1
    if counts["GREEN_EMPTY"]:
        verdict, code = "DEAD_RUNS_FOUND", 1
    elif counts["UNKNOWN"]:
        verdict, code = "UNKNOWN", 2
    else:
        verdict, code = "CLEAN", 0
    if a.json:
        print(json.dumps({"verdict": verdict, "counts": dict(counts), "runs": rows,
                          "streaks": {j: streak(v) for j, v in by_job.items()}}, indent=2))
        return code
    print("DEAD CRON DETECTOR %s" % VERSION)
    print("VERDICT %s" % verdict)
    print("runs=%d ok=%d green_empty=%d failed_loud=%d unknown=%d" % (
        len(rows), counts["OK"], counts["GREEN_EMPTY"], counts["FAILED_LOUD"], counts["UNKNOWN"]))
    print("")
    print("PER JOB")
    for job in sorted(by_job):
        jr = by_job[job]
        last_ok = next((r["at"] for r in reversed(jr) if r["verdict"] == "OK"), "never")
        ge = sum(1 for r in jr if r["verdict"] == "GREEN_EMPTY")
        print("  %-18s runs=%d green_empty=%d current_streak=%d last_real_work=%s" % (
            job, len(jr), ge, streak(jr), last_ok))
    flagged = [r for r in rows if r["verdict"] in ("GREEN_EMPTY", "UNKNOWN")]
    if flagged:
        print("")
        print("FLAGGED RUNS")
        for r in flagged:
            eff = "?" if r["effects"] is None else r["effects"]
            print("  %-11s %-18s %-10s %s exit=%s effects=%s/%s (%s)" % (
                r["verdict"], r["job"], r["run_id"], r["at"], r["exit_code"], eff, r["needed"], r["source"]))
    return code


if __name__ == "__main__":
    sys.exit(main())
