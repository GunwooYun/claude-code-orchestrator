# Phase 1 — research when agy is unavailable

Loaded on demand from `/feature` Phase 1 B.

**리서치를 건너뛰지 않는다.** 같은 목적을 Claude 자신의 도구로 달성하되, 더
좁아진다는 사실을 문서와 사용자에게 남긴다.

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true
- prompt: |
    Research for: {feature}. agy is unavailable ({state}), so use your own tools.

    1. Repository: use Grep/Glob/Read to find the code this feature touches.
       This is TARGETED, not exhaustive — record which paths you actually read.

    2. External: use WebSearch/WebFetch only for what the repository cannot
       answer (library choice, breaking changes). Cite URLs.

    3. Save to .claude/docs/research/{feature}.md, and make the FIRST LINE:
       > 조사 도구: Claude (WebSearch/Grep) — agy 사용 불가 ({state}, {date}).
       > 레포 전수 조사가 아니며, 읽은 경로는 아래 "조사 범위"에 적혀 있다.

    4. Add a "조사 범위" section listing the paths read and the queries run.

    5. Return CONCISE summary (5-7 bullets) AND a "못 본 것" list — what a
       repository-wide sweep would have covered and this did not.
```

그리고 **사용자에게 한 번 알린다**: 어떤 상태인지, 무엇으로 대체했는지, 무엇이
불가능해졌는지(영상·음성 분석은 대체 불가). 매번 반복하지 않는다.

Phase 3 의 deep-reasoning 프롬프트에 **"리서치가 좁다"는 사실을 함께 넘긴다** —
설계 리뷰가 근거의 폭을 감안해서 판단해야 한다.

---
