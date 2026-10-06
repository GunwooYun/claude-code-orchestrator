"""
Differential test: log-cli-tools' `direct` verdict against real bash.

`direct` claims the Bash tool's stdout is agy's output alone and agy's stderr
reaches the tool (so a soft-deny notice would be seen). Every review round
before this test found a shell shape where that claim was false, because the
hook's reading of a command and bash's disagreed. Here bash is the judge: each
command runs with a fake `agy` that prints known markers, and whenever the
hook says `direct`, stdout must be exactly agy's and stderr must hold agy's.
"""

import importlib.util
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / ".claude" / "hooks" / "log-cli-tools.py"
spec = importlib.util.spec_from_file_location("log_cli_tools_oracle", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

AGY_OUT = "AGY_STDOUT_MARK"
AGY_ERR = "AGY_STDERR_MARK"
FAKE_AGY = f"#!/bin/sh\nprintf '{AGY_OUT}\\n'\nprintf '{AGY_ERR}\\n' >&2\n"
SEED = 20261006
RANDOM_CASES = 600
RUN_TIMEOUT_SECONDS = 5

# Inputs the reviews reported, kept verbatim.
REVIEW_INPUTS = (
    "agy -p q --add-dir ~/c#proj > out.log; echo EXIT_CODE=$?",
    "agy -p q#tag || echo FAILED",
    "agy -p q # note \\\necho hi",
    "agy -p q --add-dir ~/it\\'s#1 > out.log; echo EXIT_CODE=$?",
    "agy -p $'it\\'s' > out.log; echo it\\'s",
    "agy -p q 2>err.log",
    "agy -p q 2>&1",
    "agy -p q 2>/dev/stdout",
    "agy -p q || echo FETCH FAILED",
    "agy -p q; echo EXIT_CODE=$?",
    'agy -p "q"\necho done > marker.txt',
    "cat > run.sh <<'EOF'\nagy -p \"Research X\" --model m\nEOF",
)

# Pieces combined at random. Only harmless commands, run in a temp directory.
PREFIXES = (
    "",
    "X=1 ",
    "env ",
    "nohup ",
    "! ",
    "cd . && ",
    "echo pre; ",
    "# c\n",
    "true\n",
)
PROMPTS = (
    "q", '"q"', "'q'", '"a #b"', "q#t", "it\\'s", "$'it\\'s'", '"$(echo p)"',
    '"x \\"y\\" #z"', "'C# tips'", '"line1\nline2"', "`echo p`", '$"q"',
)  # fmt: skip
MIDDLES = ("", " --model m", " --add-dir ~/c#p", " -x 42", " #c")
REDIRECTS = (
    "", " 2>e.log", " 2>/dev/null", " >o.log", " 2>&1", " >&2", " <in.txt",
    " 2>/dev/stdout", " &>a.log", " 2>e.log >o.log",
)  # fmt: skip
SUFFIXES = (
    "", " | tee t.log", " | tee -a t.log", " | cat", " ; echo X", " || echo F",
    " && echo D", " # note", " # it's", "\necho N", " \\\necho C", " | tee t.log > u.log",
    "; echo it\\'s",
)  # fmt: skip


def random_commands(count: int) -> list[str]:
    """Combine one piece of each kind; half the time a piece is its plainest
    form, so enough commands land near the `direct` boundary to test it."""
    rng = random.Random(SEED)
    parts = (PREFIXES, ("agy -p ",), PROMPTS, MIDDLES, REDIRECTS, SUFFIXES)
    return [
        "".join(rng.choice(part) if rng.random() < 0.5 else part[0] for part in parts)
        for _ in range(count)
    ]


@unittest.skipUnless(shutil.which("bash"), "bash is the oracle")
class DirectMatchesBashTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        agy = bin_dir / "agy"
        agy.write_text(FAKE_AGY, encoding="utf-8")
        agy.chmod(0o755)
        (self.root / "in.txt").write_text("input\n", encoding="utf-8")
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(self.root),
        }

    def run_bash(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", command],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
        )

    def assert_direct_is_true(self, command: str) -> bool:
        """Return whether the hook said direct; fail if bash disagrees."""
        if hook.classify_stdout_target(command) != "direct":
            return False
        result = self.run_bash(command)
        self.assertEqual(
            result.stdout,
            f"{AGY_OUT}\n",
            f"judged direct, but stdout is not agy's alone: {command!r}",
        )
        self.assertIn(
            AGY_ERR,
            result.stderr,
            f"judged direct, but agy's stderr (soft-deny channel) is hidden: {command!r}",
        )
        return True

    def test_review_inputs(self) -> None:
        for command in REVIEW_INPUTS:
            with self.subTest(command=command):
                self.assert_direct_is_true(command)

    def test_random_combinations(self) -> None:
        judged = 0
        for command in random_commands(RANDOM_CASES):
            with self.subTest(command=command):
                judged += self.assert_direct_is_true(command)
        # The oracle proves nothing if nothing is ever judged direct.
        self.assertGreater(judged, 10, "too few direct verdicts to test anything")


if __name__ == "__main__":
    unittest.main()
