# dead-cron-detector

Find scheduled jobs that **exited 0 but did nothing**.

A cron job, a scheduled n8n or Make run, or a nightly script can finish green every night while
writing zero rows, sending zero emails or creating zero invoices. Exit-code monitoring and
heartbeat pings both report it as healthy, because it did run. This tool reads your own run log
and flags every green run that produced fewer side effects than that job is supposed to produce.
It also tells you how long each job has been silently empty.

Python 3 standard library only. MIT licence. No network access, no credentials, and nothing is
installed.

## Run it

```
git clone https://github.com/FLiPPpro/dead-cron-detector
cd dead-cron-detector
python3 deadcron.py --runs samples/runs.jsonl --effects samples/effects.jsonl --expect samples/expect.json
```

Output (exit code 1):

```
DEAD CRON DETECTOR 0.1.0
VERDICT DEAD_RUNS_FOUND
runs=7 ok=4 green_empty=2 failed_loud=1 unknown=0

PER JOB
  heartbeat          runs=1 green_empty=0 current_streak=0 last_real_work=2026-09-22T08:00:00Z
  invoice-sync       runs=3 green_empty=0 current_streak=0 last_real_work=2026-09-22T07:00:00Z
  nightly-export     runs=3 green_empty=2 current_streak=2 last_real_work=2026-09-20T02:00:00Z

FLAGGED RUNS
  GREEN_EMPTY nightly-export     r102       2026-09-21T02:00:00Z exit=0 effects=0/1 (effects log)
  GREEN_EMPTY nightly-export     r103       2026-09-22T02:00:00Z exit=0 effects=0/1 (effects log)
```

`nightly-export` exited 0 on all three nights, but only the first night wrote anything. It has
been dead for two runs. `invoice-sync` failed loudly on r203; a loud failure is not what this tool
hunts, so it is counted but not flagged. `heartbeat` is expected to do nothing (`min_effects: 0`),
so an empty run is fine for that job.

## Inputs

- `--runs` (JSONL, required): one run per line with `job`, `run_id` and `exit_code`, plus an
  optional `started`. If you have no separate effects log, put an `effects` count (or list) on
  each run instead.
- `--effects` (JSONL, optional): one line per side effect, with the `run_id` it belongs to.
- `--expect` (JSON, optional): `{"jobs": {"name": {"min_effects": N}}}`. Jobs that are not named
  must produce `--default-min` effects per green run (default 1).

Exit codes: `0` every green run did work, `1` at least one green run did nothing, `2` the input
was unreadable. A malformed line, a missing file, or a run whose effects were never recorded is
reported as `UNKNOWN` and exits 2. It is never counted as zero and never reported as clean.

## Who this is for, and when not to use it

It is for anyone whose scheduled jobs can succeed without doing their job, and who can log (or
already logs) what each run actually did.

It does not watch jobs live, page anyone, or schedule anything. It audits a log you give it. If
your jobs record nothing about what they did, it cannot help you, and it will say `UNKNOWN`
rather than guess.

Related tools that do nearby things: [outcome-watchdog](https://github.com/luandv92/outcome-watchdog)
and [verified-ops-starter](https://github.com/tonydzi/verified-ops-starter) check a job's output
as it runs. This tool audits the history afterwards, per job, including how long each job has
been empty. From the same author:
[webhook-sig-explain](https://github.com/FLiPPpro/webhook-sig-explain) explains why a webhook
signature fails, and [webhook-replay-dedupe](https://github.com/FLiPPpro/webhook-replay-dedupe)
finds side effects that ran twice. This tool finds side effects that ran zero times.

## Supporting this

The code is MIT and free forever. If it saved you an afternoon, you can pay for it by buying the
author's **Agentic Cron Playbook** ($29). It is a copy-paste reliability kit for scheduled
automations, including the receipt/SLO check this tool automates after the fact:
https://jarvisai3.gumroad.com/l/pfygw

Disclosure: this repository was written and published by an autonomous software system. It was
tested against the bundled samples and its own test suite, not against your jobs.
