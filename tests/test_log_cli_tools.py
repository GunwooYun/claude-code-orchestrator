"""Tests for .claude/hooks/log-cli-tools.py (agy command detection and parsing)."""

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

HOOK_PATH = Path(__file__).parent.parent / ".claude" / "hooks" / "log-cli-tools.py"
spec = importlib.util.spec_from_file_location("log_cli_tools", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class DetectAgyInvocationTests(unittest.TestCase):
    def assert_prompt(self, command: str, expected: str | None) -> None:
        args = hook.find_agy_args(command)
        prompt = hook.extract_agy_prompt(args) if args else None
        self.assertEqual(prompt, expected, command)

    # --- real invocations -------------------------------------------------
    def test_simple_call(self):
        self.assert_prompt('agy -p "Research httpx"', "Research httpx")

    def test_long_flag_aliases(self):
        self.assert_prompt('agy --print "A"', "A")
        self.assert_prompt("agy --prompt 'B'", "B")

    def test_flag_before_prompt(self):
        self.assert_prompt(
            'agy --model gemini-3.1-pro-high -p "Research x"', "Research x"
        )

    def test_flags_after_prompt(self):
        self.assert_prompt(
            'agy -p "Analyze repo" --dangerously-skip-permissions --sandbox --print-timeout 10m',
            "Analyze repo",
        )

    def test_multiline_prompt(self):
        self.assert_prompt('agy -p "Line one\nLine two"', "Line one\nLine two")

    def test_escaped_quotes_inside_prompt(self):
        self.assert_prompt('agy -p "Say \\"hi\\""', 'Say "hi"')

    def test_pipeline_and_chaining(self):
        self.assert_prompt('cat f | agy -p "Summarize"', "Summarize")
        self.assert_prompt('cd /tmp && agy -p "Analyze"', "Analyze")
        self.assert_prompt(
            'export PATH=/x:$PATH; agy -p "After export"', "After export"
        )

    def test_wrappers_and_env(self):
        self.assert_prompt('timeout 60 agy -p "Wrapped"', "Wrapped")
        self.assert_prompt('FOO=bar agy -p "Env"', "Env")

    def test_command_substitution_and_path_prefix(self):
        self.assert_prompt('result=$(agy -p "Sub")', "Sub")
        self.assert_prompt('/usr/local/bin/agy -p "Abs path"', "Abs path")
        self.assert_prompt('~/.local/bin/agy -p "Home path"', "Home path")

    # --- non-invocations ---------------------------------------------------
    def test_quoted_mention_inside_grep_is_ignored(self):
        self.assert_prompt("grep -rn 'agy -p \"x\"' .", None)

    def test_echo_of_agy_string_is_ignored(self):
        self.assert_prompt('echo "agy -p \\"x\\""', None)

    def test_heredoc_python_literal_is_ignored(self):
        cmd = "python3 - <<'EOF'\nimport re\ns = re.sub(r'(agy -p \"x\")', '', s)\nEOF"
        self.assert_prompt(cmd, None)

    def test_substring_words_are_ignored(self):
        self.assert_prompt("echo strategy", None)
        self.assert_prompt("agy models", None)
        self.assert_prompt("agy --help", None)


class PositionalPromptTests(unittest.TestCase):
    def test_flag_directly_after_p_is_not_the_prompt(self):
        args = ["agy", "-p", "--model", "gemini-3.7-flash-low", "q"]
        self.assertEqual(hook.extract_agy_prompt(args), "q")

    def test_value_flags_are_skipped(self):
        args = [
            "agy",
            "-p",
            "--output-format",
            "json",
            "--print-timeout",
            "10m",
            "real prompt",
        ]
        self.assertEqual(hook.extract_agy_prompt(args), "real prompt")

    def test_print_flag_without_prompt(self):
        self.assertIsNone(hook.extract_agy_prompt(["agy", "-p"]))

    def test_no_print_flag_is_not_print_mode(self):
        self.assertIsNone(hook.extract_agy_prompt(["agy", "models"]))

    def test_loop_body_is_detected(self):
        self.assertEqual(
            hook.extract_agy_prompt(
                hook.find_agy_args('for f in a b; do agy -p "Sum $f"; done')
            ),
            "Sum $f",
        )


class ExtractModelTests(unittest.TestCase):
    def test_model_space_form(self):
        self.assertEqual(
            hook.extract_model(["agy", "--model", "gemini-3.1-pro-high", "-p", "x"]),
            "gemini-3.1-pro-high",
        )

    def test_model_equals_form(self):
        self.assertEqual(
            hook.extract_model(["agy", "-p", "x", "--model=gemini-3.7-flash-low"]),
            "gemini-3.7-flash-low",
        )

    def test_model_missing(self):
        self.assertIsNone(hook.extract_model(["agy", "-p", "x"]))


class DetermineSuccessTests(unittest.TestCase):
    def test_plain_text_output(self):
        self.assertTrue(hook.determine_success("answer", ""))
        self.assertFalse(hook.determine_success("", ""))

    def test_json_success(self):
        self.assertTrue(
            hook.determine_success('{"status":"SUCCESS","response":"OK"}', "")
        )

    def test_json_success_with_empty_response_is_failure(self):
        self.assertFalse(
            hook.determine_success('{"status":"SUCCESS","response":""}', "")
        )

    def test_json_error_status(self):
        self.assertFalse(
            hook.determine_success('{"status":"ERROR","response":"x"}', "")
        )

    def test_soft_deny_marker_on_stderr(self):
        stderr = 'no output produced — a tool required the "read_file" permission ... auto-denied.'
        self.assertFalse(hook.determine_success("", stderr))

    def test_soft_deny_words_in_stdout_are_not_a_failure(self):
        stdout = "In headless mode, tools without permission are auto-denied and no output produced."
        self.assertTrue(hook.determine_success(stdout, ""))

    def test_stream_json_uses_last_result_line(self):
        stream = '{"event":"init"}\n{"event":"step_update"}\n{"status":"ERROR","response":"","error":"x"}'
        self.assertFalse(hook.determine_success(stream, ""))
        stream_ok = '{"event":"init"}\n{"status":"SUCCESS","response":"done"}'
        self.assertTrue(hook.determine_success(stream_ok, ""))


class ProcessHookInputTests(unittest.TestCase):
    def test_non_dict_payload_is_ignored(self):
        self.assertIsNone(hook.process_hook_input([1, 2]))
        self.assertIsNone(hook.process_hook_input("agy -p x"))

    def test_null_tool_input_is_ignored(self):
        self.assertIsNone(
            hook.process_hook_input({"tool_name": "Bash", "tool_input": None})
        )

    def test_non_bash_tool_is_ignored(self):
        self.assertIsNone(
            hook.process_hook_input(
                {"tool_name": "Read", "tool_input": {"command": 'agy -p "x"'}}
            )
        )

    def test_string_tool_response_is_accepted(self):
        entry = hook.process_hook_input(
            {
                "tool_name": "Bash",
                "tool_input": {"command": 'agy -p "x"'},
                "tool_response": "plain text answer",
            }
        )
        self.assertIsNotNone(entry)
        self.assertTrue(entry["success"])

    def test_log_entry_writes_one_json_line(self):
        import json as _json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            original_dir, original_file = hook.LOG_DIR, hook.LOG_FILE
            hook.LOG_DIR = Path(tmp)
            hook.LOG_FILE = Path(tmp) / "cli-tools.jsonl"
            try:
                hook.log_entry({"tool": "antigravity", "prompt": "한글"})
                lines = hook.LOG_FILE.read_text(encoding="utf-8").splitlines()
            finally:
                hook.LOG_DIR, hook.LOG_FILE = original_dir, original_file
        self.assertEqual(len(lines), 1)
        self.assertEqual(_json.loads(lines[0])["prompt"], "한글")


class SoftDenySuccessTests(unittest.TestCase):
    """
    The success flag must reflect agy's headless soft-deny.

    This is not just a log field: checkpoint.py renders it as [OK] / [FAILED] in
    the session history. A regression records a DENIED agy call as a success, so
    a later session reads "we researched that" when nothing was researched — the
    exact failure `CLAUDE.md` 운영 주의사항 singles out. Measured by an
    independent review: removing the soft-deny branch left all 312 tests green.
    """

    def test_a_soft_denied_call_is_not_a_success(self) -> None:
        for marker in hook.SOFT_DENY_MARKERS:
            with self.subTest(marker=marker):
                self.assertFalse(
                    hook.determine_success("some answer text", f"warning: {marker}\n"),
                    f"stderr containing {marker!r} was counted as success",
                )

    def test_an_empty_answer_is_not_a_success(self) -> None:
        self.assertFalse(hook.determine_success("", ""))
        self.assertFalse(hook.determine_success("   \n", ""))

    def test_a_json_result_is_gated_on_status_and_response(self) -> None:
        self.assertFalse(
            hook.determine_success('{"status": "SUCCESS", "response": ""}', ""),
            "an empty response with status SUCCESS is the soft-deny shape",
        )
        self.assertFalse(
            hook.determine_success('{"status": "ERROR", "response": "text"}', "")
        )

    def test_a_real_answer_is_a_success(self) -> None:
        """The flag must not be achieved by calling everything a failure."""
        self.assertTrue(hook.determine_success("a real answer", ""))
        self.assertTrue(
            hook.determine_success('{"status": "SUCCESS", "response": "text"}', "")
        )
        self.assertTrue(
            hook.determine_success("a real answer", "note: cache warmed\n"),
            "ordinary stderr noise must not mark a good call as failed",
        )


class AllowlistTargetTests(unittest.TestCase):
    """
    Only one shape is `direct` — the one call whose stdout can be read as agy's
    answer and whose stderr reaches the tool: a single-line `agy …` on its
    own, with at most `<file` and a final `| tee …`, plainly quoted. NOT
    `2>file` — it hides the soft-deny notice (see
    test_a_stderr_redirect_is_not_direct). Everything else is unknown. Rounds
    of parsing every shell shape kept producing new false successes (an
    adopting project logged 10 of 28 calls as successes from `EXIT_CODE=0`
    echoes); tests/test_log_cli_tools_oracle.py checks each verdict in bash.
    """

    def assert_target(self, command: str, expected: str) -> None:
        self.assertEqual(hook.classify_stdout_target(command), expected, command)

    def test_the_simple_shapes_are_direct(self) -> None:
        for command in (
            'agy -p "q" --model x',
            'agy -p "Issue #42 in C#"',
            "agy -p 'C# tips'",
            'X="a#b" agy -p q',
            'agy --prompt="Issue #42"',
            'X="a b#c" agy -p q',
            "agy -p q < in.txt",
            "agy -p q | tee out.md",
            "agy -p q | tee -a out.md",
            "env X=1 agy -p q",
            "! agy -p q",
            "nohup agy -p q",
            'agy -p "line1\nline2"',
            "# T1\nagy -p q",
            "# don't redirect\n\nagy -p q",
        ):
            with self.subTest(command=command):
                self.assert_target(command, "direct")

    def test_characters_that_make_quoting_ambiguous_are_never_direct(self) -> None:
        # Isolated review of 84cdf2b: shlex and bash disagree on backslash
        # escapes and `$'…'`, which hid a redirect and `; echo` inside what
        # shlex took for a quoted word — two false successes. A backslash,
        # `$'`, `$"` or a backtick now leaves the call unjudged.
        for command in (
            "agy -p q --add-dir ~/it\\'s#1 > out.log; echo EXIT_CODE=$?",
            "agy -p $'it\\'s' > out.log; echo it\\'s",
            'agy -p "Explain \\"foo\\" in C#"',
            "agy -p q \\\n  --model x",
            'agy -p $"q"',
            "agy -p `cat p.txt`",
            # Isolated review of 0cc9cf0: bash nests quotes inside "$(…)" and
            # "${…}", a flat quote reader does not — so they are out too.
            'agy -p "$(echo "\'")" > out.log; echo EXIT_CODE=$? # \'',
            'agy -p "$(cat "Tom\'s notes.md")" > a.md; cat "$(echo "x")"',
            'agy -p "$(cat f)"',
            'X="$(cat f)" agy -p q',
            'agy -p "${X:-q}"',
        ):
            with self.subTest(command=command):
                self.assertNotEqual(hook.classify_stdout_target(command), "direct")

    def test_a_stderr_redirect_is_not_direct(self) -> None:
        # Isolated review of 84cdf2b: with stderr in a file the hook cannot see
        # a soft-deny notice, so a denied call that printed text would pass.
        for command in (
            "agy -p q 2>err.log",
            "agy -p q 2>> err.log",
            "agy -p q 2>/dev/null",
        ):
            with self.subTest(command=command):
                self.assert_target(command, "complex")

    def test_stderr_merged_into_stdout_is_not_direct(self) -> None:
        for command in (
            "agy -p q 2>&1",
            "agy -p q 2>/dev/stdout",
            "agy -p q 2>/dev/fd/1",
            "agy -p q 2>/proc/self/fd/1",
            "agy -p q 2>&1 | tee f",
            "agy -p q |& tee f",
        ):
            with self.subTest(command=command):
                self.assert_target(command, "complex")

    def test_other_commands_in_the_call_are_complex(self) -> None:
        for command in (
            "agy -p q; echo EXIT_CODE=$?",
            "agy -p q || echo FETCH FAILED",
            "agy -p q && echo done",
            "cd /tmp && agy -p q",
            "agy -p q\necho hi",
            "agy -p q # c\necho hi",
            "agy -p q \\\\\necho hi",
            "agy -p q &",
            "nohup agy -p q &",
            "timeout 60 agy -p q",
            "agy -p q | tee f | cat",
            "agy -p q | tee f > g",
            "for f in a; do agy -p q; done",
            "{ agy -p q; }",
            "agy -p q <<< text",
            "agy -p q <<EOF\nx\nEOF",
            "agy -p q # don't",
        ):
            with self.subTest(command=command):
                self.assert_target(command, "complex")

    def test_an_unquoted_hash_after_the_command_starts_is_never_direct(self) -> None:
        # PR #31 review: shlex read a mid-word `#` as a comment where bash does
        # not, so the rest of the line — a redirect, `|| echo`, a continued
        # line — vanished and the call was logged as a success. An unquoted `#`
        # (inline comment included) now leaves the call unjudged; full-line
        # comments before the command stay allowed.
        for command in (
            "agy -p q --add-dir ~/c#proj > out.log; echo EXIT_CODE=$?",
            "agy -p q#tag || echo FAILED",
            "agy -p q # note \\\necho hi",
            'agy -p "q" --model x   # T1',
            'agy -p "q" # save > later',
        ):
            with self.subTest(command=command):
                self.assertNotEqual(hook.classify_stdout_target(command), "direct")

    def test_truncated_commands_never_raise_and_are_not_direct(self) -> None:
        for command in (
            "agy -p q |",
            "agy -p q 2>",
            "agy -p q | tee >",
            "agy -p q )",
            "x=$(agy -p q",
            "agy -p q <",
            "agy -p q |&",
        ):
            with self.subTest(command=command):
                self.assertNotEqual(hook.classify_stdout_target(command), "direct")

    def test_coarse_labels_name_the_obvious_destination(self) -> None:
        self.assert_target("agy -p q > out.txt", "file:out.txt")
        self.assert_target("agy -p q &> all.log", "file:all.log")
        self.assert_target("agy -p q >&2", "stderr")
        self.assert_target("agy -p q | jq .response", "pipe:jq")
        self.assert_target("echo $(agy -p q)", "substitution")
        self.assert_target("r=$(agy -p q); echo $r", "substitution")

    def test_an_unquoted_digit_before_a_redirect_is_an_argument(self) -> None:
        self.assert_target("agy -p 2 >err", "file:err")
        self.assert_target('agy -p "2">err', "file:err")
        self.assert_target("agy -p q --conversation 42 > out.log", "file:out.log")

    def test_text_that_only_mentions_agy_is_not_a_call(self) -> None:
        for command in (
            "cat > run.sh <<'EOF'\nagy -p \"Research X\" --model m\nEOF",
            'echo "$(agy -p q)"',
        ):
            with self.subTest(command=command):
                self.assertIsNone(hook.find_agy_args(command))


class AllowlistEntryTests(unittest.TestCase):
    def entry(self, command: str, stdout: str, stderr: str = "") -> dict:
        built = hook.build_entry(command, {"stdout": stdout, "stderr": stderr})
        self.assertIsNotNone(built, command)
        return built or {}

    def test_direct_keeps_the_answer_and_judges_it(self) -> None:
        entry = self.entry("agy -p q < in.txt", "answer")
        self.assertIs(entry["success"], True)
        self.assertEqual(entry["response"], "answer")
        self.assertEqual(entry["stdout_target"], "direct")
        self.assertIs(self.entry("agy -p q", "")["success"], False)

    def test_not_direct_is_unknown_with_a_blank_response(self) -> None:
        for command, stdout in (
            ("agy -p q > out.txt; echo EXIT_CODE=$?", "EXIT_CODE=0"),
            ("agy -p q || echo FETCH FAILED", "FETCH FAILED"),
            ("agy -p q | jq -r .response", "answer"),
            ("agy -p q 2>&1", "warning: auto-denied read_file"),
            ("agy -p q 2>/dev/stdout", "no output produced"),
        ):
            with self.subTest(command=command):
                entry = self.entry(command, stdout)
                self.assertIsNone(entry["success"])
                self.assertEqual(entry["response"], "")

    def test_an_envelope_does_not_rescue_a_non_direct_call(self) -> None:
        # It may come from another command or another agy call in the same
        # Bash call; "never a success when not direct" is what the docs promise.
        entry = self.entry(
            "agy -p A --output-format json > a.json; agy -p B --output-format json",
            '{"status":"SUCCESS","response":"b"}',
        )
        self.assertIsNone(entry["success"])

    def test_soft_deny_on_stderr_is_a_failure_whatever_the_target(self) -> None:
        entry = self.entry("agy -p q | jq .", "", "warning: auto-denied read_file")
        self.assertIs(entry["success"], False)

    def test_direct_envelope_rules(self) -> None:
        self.assertIs(
            self.entry("agy -p q", '{"status":"SUCCESS","response":"x"}')["success"],
            True,
        )
        self.assertIs(self.entry("agy -p q", '{"status":"ERROR"}')["success"], False)
        # A plain answer that merely contains a JSON example mid-text is plain text.
        self.assertIs(
            self.entry(
                "agy -p q", 'Example:\n{"status":"ERROR","response":""}\nThat is all.'
            )["success"],
            True,
        )

    def test_the_mid_word_hash_false_successes_are_unknown(self) -> None:
        for command, stdout in (
            ("agy -p q --add-dir ~/c#proj > out.log; echo EXIT_CODE=$?", "EXIT_CODE=0"),
            ("agy -p q#tag || echo FAILED", "FAILED"),
            ("agy -p q # note \\\necho hi", "hi"),
        ):
            with self.subTest(command=command):
                entry = self.entry(command, stdout)
                self.assertIsNone(entry["success"])
                self.assertEqual(entry["response"], "")

    def test_a_background_call_is_unknown(self) -> None:
        # run_in_background: stdout is the harness's "running in background"
        # notice, not agy's output (PR #31 review).
        entry = hook.process_hook_input(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "agy -p q", "run_in_background": True},
                "tool_response": {
                    "stdout": "Command running in background",
                    "stderr": "",
                },
            }
        )
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["stdout_target"], "background")
        self.assertIsNone(entry["success"])
        self.assertEqual(entry["response"], "")
        foreground = hook.process_hook_input(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "agy -p q", "run_in_background": False},
                "tool_response": {"stdout": "answer", "stderr": ""},
            }
        )
        assert foreground is not None
        self.assertIs(foreground["success"], True)

    def test_a_parser_gap_is_unknown(self) -> None:
        # Fault injection: the classifier is replaced only to make it raise.
        broken = mock.Mock(side_effect=RuntimeError("parser gap"))
        with mock.patch.object(hook, "classify_stdout_target", broken):
            entry = self.entry("agy -p q", "A")
        broken.assert_called_once()
        self.assertEqual(entry["stdout_target"], "unclassified")
        self.assertIsNone(entry["success"])
        self.assertEqual(entry["response"], "")


class PromptWithRedirectionsTests(unittest.TestCase):
    def test_redirections_are_not_read_as_the_prompt(self) -> None:
        # Isolated review of 84cdf2b: `agy 2>err.log -p "q"` logged `2>`.
        for command in (
            'agy 2>err.log -p "q"',
            'agy < in.txt -p "q"',
            'agy -p "q" > o',
        ):
            with self.subTest(command=command):
                args = hook.find_agy_args(command)
                self.assertEqual(hook.extract_agy_prompt(args or []), "q")


class BuildEntryTests(unittest.TestCase):
    def test_builds_entry_for_real_call(self):
        entry = hook.build_entry('agy -p "Q" --model=m1', {"stdout": "A", "stderr": ""})
        self.assertEqual(entry["tool"], "antigravity")
        self.assertEqual(entry["model"], "m1")
        self.assertEqual(entry["prompt"], "Q")
        self.assertTrue(entry["success"])

    def test_returns_none_for_non_call(self):
        self.assertIsNone(hook.build_entry("grep 'agy -p \"x\"' .", {"stdout": "hit"}))


if __name__ == "__main__":
    unittest.main()
