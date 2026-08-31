#!/usr/bin/env python3
"""
UserPromptSubmit hook: Route to appropriate agent based on user intent.

Analyzes user prompts and suggests the most appropriate agent
(deep-reasoning subagent for design/debug, Antigravity CLI for research/multimodal).
"""

import json
import sys

# Triggers for the deep-reasoning subagent (design, debugging, deep reasoning)
DEEP_REASONING_TRIGGERS = {
    "ko": [
        "설계", "어떻게 설계", "아키텍처",
        "왜 움직이지 않는다", "오류", "버그", "디버깅",
        "어느 쪽이 좋다", "비교해", "트레이드오프",
        "구현 방법", "어떻게 구현",
        "리팩토링",
        "리뷰", "보여줘",
        "생각해", "분석해", "깊게",
    ],
    "en": [
        "design", "architecture", "architect",
        "debug", "error", "bug", "not working", "fails",
        "compare", "trade-off", "tradeoff", "which is better",
        "how to implement", "implementation",
        "refactor", "simplify",
        "review", "check this",
        "think", "analyze", "deeply",
    ],
}

# Triggers for Antigravity CLI (research, multimodal, large context)
ANTIGRAVITY_TRIGGERS = {
    "ko": [
        "검사해", "리서치해", "조사해",
        "동영상", "오디오", "이미지",
        "코드베이스 전체", "리포지토리 전체",
        "최신", "문서",
        "라이브러리", "패키지",
    ],
    "en": [
        "research", "investigate", "look up", "find out",
        "pdf", "video", "audio", "image",
        "entire codebase", "whole repository",
        "latest", "documentation", "docs",
        "library", "package", "framework",
    ],
}


def detect_agent(prompt: str) -> tuple[str | None, str]:
    """Detect which agent should handle this prompt."""
    prompt_lower = prompt.lower()

    # Check deep-reasoning triggers
    for triggers in DEEP_REASONING_TRIGGERS.values():
        for trigger in triggers:
            if trigger in prompt_lower:
                return "deep-reasoning", trigger

    # Check Antigravity triggers
    for triggers in ANTIGRAVITY_TRIGGERS.values():
        for trigger in triggers:
            if trigger in prompt_lower:
                return "antigravity", trigger

    return None, ""


def main():
    try:
        data = json.load(sys.stdin)
        prompt = data.get("prompt", "")

        # Skip short prompts
        if len(prompt) < 10:
            sys.exit(0)

        agent, trigger = detect_agent(prompt)

        if agent == "deep-reasoning":
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Agent Routing] Detected '{trigger}' - this task may benefit from "
                        "deep reasoning in an isolated context. Consider: Task tool with "
                        "subagent_type='deep-reasoning' for design decisions, debugging, "
                        "or complex analysis."
                    )
                }
            }
            print(json.dumps(output))

        elif agent == "antigravity":
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"[Agent Routing] Detected '{trigger}' - this task may benefit from "
                        "Antigravity CLI's research capabilities. Consider: "
                        '`agy -p "Research: {topic}" --model {slug per Model Policy}` (via general-purpose subagent) '
                        "for documentation, library research, or multimodal content."
                    )
                }
            }
            print(json.dumps(output))

        sys.exit(0)

    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
