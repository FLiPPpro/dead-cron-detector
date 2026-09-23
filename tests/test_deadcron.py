import io, os, sys, unittest
from contextlib import redirect_stdout
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import deadcron
S = os.path.join(os.path.dirname(HERE), "samples")


def run(*args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deadcron.main(list(args))
    return code, buf.getvalue()


class T(unittest.TestCase):
    def test_sample_finds_dead_runs(self):
        code, out = run("--runs", S + "/runs.jsonl", "--effects", S + "/effects.jsonl", "--expect", S + "/expect.json")
        self.assertEqual(code, 1)
        self.assertIn("VERDICT DEAD_RUNS_FOUND", out)
        self.assertIn("green_empty=2", out)
        self.assertIn("current_streak=2", out)

    def test_zero_expected_job_is_ok(self):
        code, out = run("--runs", S + "/runs.jsonl", "--effects", S + "/effects.jsonl", "--expect", S + "/expect.json")
        self.assertIn("heartbeat          runs=1 green_empty=0", out)

    def test_failed_run_is_loud_not_dead(self):
        code, out = run("--runs", S + "/runs.jsonl", "--effects", S + "/effects.jsonl", "--expect", S + "/expect.json")
        self.assertIn("failed_loud=1", out)
        self.assertNotIn("r203", out.split("FLAGGED RUNS")[1])

    def test_clean(self):
        self.assertEqual(run("--runs", S + "/clean.jsonl")[0], 0)

    def test_broken_input_is_never_clean(self):
        code, out = run("--runs", S + "/broken.jsonl")
        self.assertEqual(code, 2)
        self.assertIn("VERDICT UNKNOWN", out)
        self.assertNotIn("CLEAN", out)

    def test_missing_file_is_never_clean(self):
        self.assertEqual(run("--runs", S + "/nope.jsonl")[0], 2)

    def test_unrecorded_effects_are_unknown_not_zero(self):
        code, out = run("--runs", S + "/runs.jsonl")
        self.assertEqual(code, 2)
        self.assertIn("VERDICT UNKNOWN", out)
        self.assertIn("no effects recorded", out)


if __name__ == "__main__":
    unittest.main()
