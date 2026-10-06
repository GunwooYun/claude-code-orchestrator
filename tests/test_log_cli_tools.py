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


class EnvelopeWithTrailingLinesTests(unittest.TestCase):
    """
    V9: `agy ... --output-format json; echo EXIT_CODE=$?` puts a line after the
    envelope. The verdict must come from the envelope, not the trailing text —
    an earlier version tried only the whole stdout and its last line, so an
    ERROR envelope followed by `EXIT_CODE=1` was logged as a success.
    """

    def test_error_envelope_followed_by_echo_is_failure(self) -> None:
        stdout = '{"status":"ERROR","response":""}\nEXIT_CODE=1'
        self.assertFalse(hook.determine_success(stdout, ""))

    def test_empty_success_envelope_followed_by_echo_is_failure(self) -> None:
        stdout = '{"status":"SUCCESS","response":""}\nEXIT_CODE=0\n'
        self.assertFalse(hook.determine_success(stdout, ""))

    def test_success_envelope_followed_by_echo_is_success(self) -> None:
        stdout = '{"status":"SUCCESS","response":"answer"}\nEXIT_CODE=0'
        self.assertTrue(hook.determine_success(stdout, ""))


class StdoutTargetTests(unittest.TestCase):
    """
    Whether the Bash tool's stdout IS agy's stdout. When it is not, the hook
    must not read it as agy's answer: an adopting project's log held 28 calls,
    of which 10 were `EXIT_CODE=0`-style text from a redirected call marked as
    a success.
    """

    def assert_target(self, command: str, expected: str) -> None:
        self.assertEqual(hook.classify_stdout_target(command), expected, command)

    # V1, V2
    def test_stdout_file_redirects(self) -> None:
        self.assert_target('agy -p "q" > out.log; echo EXIT_CODE=$?', "file:out.log")
        self.assert_target('agy -p "q" >out.log', "file:out.log")
        self.assert_target('agy -p "q" >> out.log', "file:out.log")
        self.assert_target('agy -p "q" >| out.log', "file:out.log")
        self.assert_target('agy -p "q" &> all.log', "file:all.log")
        self.assert_target('agy -p "q" &>> all.log', "file:all.log")
        self.assert_target('agy -p "q" 1> out.log', "file:out.log")
        self.assert_target('agy -p "q" >& out.log', "file:out.log")

    # V3
    def test_stderr_and_input_redirects_keep_stdout_direct(self) -> None:
        self.assert_target('agy -p "q" 2> err.log', "direct")
        self.assert_target('agy -p "q" 2>err.log', "direct")
        self.assert_target('agy -p "q" 2>> err.log', "direct")
        self.assert_target('agy -p "q" 2>&1', "direct")
        self.assert_target('agy -p "q" < in.txt', "direct")
        self.assert_target('agy -p "q"', "direct")

    # V4
    def test_stdout_to_stderr_and_redirect_order(self) -> None:
        self.assert_target('agy -p "q" >&2', "stderr")
        self.assert_target('agy -p "q" 1>&2', "stderr")
        self.assert_target('agy -p "q" 2>&1 >/dev/null', "file:/dev/null")
        self.assert_target('agy -p "q" >/dev/null 2>&1', "file:/dev/null")
        # The last redirection touching stdout wins.
        self.assert_target('agy -p "q" > a.log > b.log', "file:b.log")
        self.assert_target('agy -p "q" >&2 > out.log', "file:out.log")
        self.assert_target('agy -p "q" > out.log >&2', "stderr")

    # V5
    def test_command_substitution_and_subshell(self) -> None:
        self.assert_target('result=$(agy -p "q")', "substitution")
        self.assert_target('result=$(agy -p "q"); echo "$result"', "substitution")
        self.assert_target('echo $(agy -p "q")', "substitution")
        self.assert_target('x=$(cd /tmp && agy -p "q"; echo done)', "substitution")
        self.assert_target('( agy -p "q" )', "direct")
        self.assert_target('(cd /tmp && agy -p "q"; echo done)', "direct")
        self.assert_target('( agy -p "q" ) > out.log', "file:out.log")

    # V6
    def test_pipes_and_tee(self) -> None:
        self.assert_target(
            'agy -p "q" --output-format json | jq -r .response', "pipe:jq"
        )
        self.assert_target('agy -p "q" |& jq .', "pipe:jq")
        self.assert_target('(agy -p "q")|jq .', "pipe:jq")
        self.assert_target('agy -p "q" | tee out.log', "direct")
        self.assert_target('agy -p "q" | tee -a out.log', "direct")
        self.assert_target('agy -p "q" 2>&1 | tee out.log', "direct")
        self.assert_target('agy -p "q" | tee out.log > /dev/null', "file:/dev/null")
        self.assert_target('agy -p "q" | tee out.log | head', "pipe:head")
        self.assert_target('agy -p "q" > out.log | jq .', "file:out.log")
        self.assert_target('agy -p "q" | FOO=1 timeout 9 jq .', "pipe:jq")

    # V7
    def test_follow_on_commands_keep_stdout_direct(self) -> None:
        self.assert_target('agy -p "q" || echo FETCH FAILED', "direct")
        self.assert_target('agy -p "q" && echo done', "direct")
        self.assert_target('agy -p "q"; echo next', "direct")
        self.assert_target('agy -p "q" &', "direct")

    # V11
    def test_malformed_input_never_raises(self) -> None:
        for command in (
            'agy -p "q" >',
            'x=$(agy -p "q"',
            'agy -p "q" ) ) > f',
            'agy -p "unbalanced > f',
            "",
        ):
            with self.subTest(command=command):
                self.assertIsInstance(hook.classify_stdout_target(command), str)


class NotDirectEntryTests(unittest.TestCase):
    """build_entry when agy's stdout did not reach the Bash tool unaltered."""

    def test_file_redirect_is_unknown_with_blank_response(self) -> None:
        entry = hook.build_entry(
            'agy -p "q" > out.log; echo EXIT_CODE=$?',
            {"stdout": "EXIT_CODE=0", "stderr": ""},
        )
        self.assertIsNone(entry["success"])
        self.assertEqual(entry["response"], "")
        self.assertEqual(entry["stdout_target"], "file:out.log")

    def test_failed_call_behind_redirect_is_not_a_success(self) -> None:
        entry = hook.build_entry(
            'agy -p "q" > out.log 2> err.log; echo EXIT_CODE=$?',
            {"stdout": "EXIT_CODE=1", "stderr": ""},
        )
        self.assertIsNone(entry["success"])

    def test_substitution_is_unknown_with_blank_response(self) -> None:
        entry = hook.build_entry(
            'r=$(agy -p "q"); echo FETCH FAILED', {"stdout": "FETCH FAILED"}
        )
        self.assertIsNone(entry["success"])
        self.assertEqual(entry["response"], "")

    # V6 (response policy)
    def test_pipe_keeps_response_but_is_unknown(self) -> None:
        entry = hook.build_entry(
            'agy -p "q" --output-format json | jq -r .response', {"stdout": "answer"}
        )
        self.assertIsNone(entry["success"])
        self.assertEqual(entry["response"], "answer")
        self.assertEqual(entry["stdout_target"], "pipe:jq")

    def test_direct_call_records_its_target(self) -> None:
        entry = hook.build_entry('agy -p "q"', {"stdout": "answer"})
        self.assertTrue(entry["success"])
        self.assertEqual(entry["stdout_target"], "direct")

    # V8
    def test_soft_deny_is_a_failure_even_when_not_direct(self) -> None:
        entry = hook.build_entry(
            'agy -p "q" > out.log',
            {"stdout": "", "stderr": "warning: auto-denied read_file"},
        )
        self.assertIs(entry["success"], False)

    # V10
    def test_envelope_decides_whatever_the_target(self) -> None:
        ok = hook.build_entry(
            'agy -p "q" --output-format json > f.json; cat f.json',
            {"stdout": '{"status":"SUCCESS","response":"answer"}'},
        )
        self.assertIs(ok["success"], True)
        failed = hook.build_entry(
            'agy -p "q" --output-format json > f.json; cat f.json',
            {"stdout": '{"status":"ERROR","response":""}'},
        )
        self.assertIs(failed["success"], False)

    def test_classification_error_falls_back_to_direct(self) -> None:
        # Fault injection: the classifier is replaced only to make it raise.
        broken = mock.Mock(side_effect=RuntimeError("parser gap"))
        with mock.patch.object(hook, "classify_stdout_target", broken):
            entry = hook.build_entry('agy -p "q" > out.log', {"stdout": "A"})
        broken.assert_called_once()
        self.assertIsNotNone(entry)
        self.assertEqual(entry["stdout_target"], "direct")


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
