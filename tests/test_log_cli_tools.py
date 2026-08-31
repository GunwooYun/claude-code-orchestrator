"""Tests for .claude/hooks/log-cli-tools.py (agy command detection and parsing)."""

import importlib.util
import unittest
from pathlib import Path

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
        self.assert_prompt('agy --model gemini-3.1-pro-high -p "Research x"', "Research x")

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
        self.assert_prompt('export PATH=/x:$PATH; agy -p "After export"', "After export")

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
        args = ["agy", "-p", "--output-format", "json", "--print-timeout", "10m", "real prompt"]
        self.assertEqual(hook.extract_agy_prompt(args), "real prompt")

    def test_print_flag_without_prompt(self):
        self.assertIsNone(hook.extract_agy_prompt(["agy", "-p"]))

    def test_no_print_flag_is_not_print_mode(self):
        self.assertIsNone(hook.extract_agy_prompt(["agy", "models"]))

    def test_loop_body_is_detected(self):
        self.assertEqual(hook.extract_agy_prompt(hook.find_agy_args('for f in a b; do agy -p "Sum $f"; done')),
                         "Sum $f")


class ExtractModelTests(unittest.TestCase):
    def test_model_space_form(self):
        self.assertEqual(hook.extract_model(["agy", "--model", "gemini-3.1-pro-high", "-p", "x"]),
                         "gemini-3.1-pro-high")

    def test_model_equals_form(self):
        self.assertEqual(hook.extract_model(["agy", "-p", "x", "--model=gemini-3.7-flash-low"]),
                         "gemini-3.7-flash-low")

    def test_model_missing(self):
        self.assertIsNone(hook.extract_model(["agy", "-p", "x"]))


class DetermineSuccessTests(unittest.TestCase):
    def test_plain_text_output(self):
        self.assertTrue(hook.determine_success("answer", ""))
        self.assertFalse(hook.determine_success("", ""))

    def test_json_success(self):
        self.assertTrue(hook.determine_success('{"status":"SUCCESS","response":"OK"}', ""))

    def test_json_success_with_empty_response_is_failure(self):
        self.assertFalse(hook.determine_success('{"status":"SUCCESS","response":""}', ""))

    def test_json_error_status(self):
        self.assertFalse(hook.determine_success('{"status":"ERROR","response":"x"}', ""))

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
        self.assertIsNone(hook.process_hook_input({"tool_name": "Bash", "tool_input": None}))

    def test_non_bash_tool_is_ignored(self):
        self.assertIsNone(hook.process_hook_input({"tool_name": "Read", "tool_input": {"command": 'agy -p "x"'}}))

    def test_string_tool_response_is_accepted(self):
        entry = hook.process_hook_input({"tool_name": "Bash", "tool_input": {"command": 'agy -p "x"'},
                                         "tool_response": "plain text answer"})
        self.assertIsNotNone(entry)
        self.assertTrue(entry["success"])

    def test_log_entry_writes_one_json_line(self):
        import tempfile, json as _json
        with tempfile.TemporaryDirectory() as tmp:
            original_dir, original_file = hook.LOG_DIR, hook.LOG_FILE
            hook.LOG_DIR = Path(tmp); hook.LOG_FILE = Path(tmp) / "cli-tools.jsonl"
            try:
                hook.log_entry({"tool": "antigravity", "prompt": "한글"})
                lines = hook.LOG_FILE.read_text(encoding="utf-8").splitlines()
            finally:
                hook.LOG_DIR, hook.LOG_FILE = original_dir, original_file
        self.assertEqual(len(lines), 1)
        self.assertEqual(_json.loads(lines[0])["prompt"], "한글")


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
