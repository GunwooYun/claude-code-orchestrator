---
paths:
  - "tests/**"
---
# Test Writing

Loaded when a test file is read or edited. Principles (verify first, break each new test once,
never edit a test to pass): `.claude/rules/testing.md`. `/initproject` adjusts the glob and adds
the project's own conventions (fixture location, naming).

## 테스트 작성

- **이름**: `test_{대상}_{조건}_{기대결과}` — 이름만 읽고 무엇이 깨졌는지 알 수 있게.
- **케이스**: 정상 경로 / 경계값(최소·최대·빈 값) / 오류 경로(잘못된 입력에서 **실제로 실패하는지**) /
  엣지(None·빈 문자열·특수문자).
- **목(mock)은 외부 의존성만.** 검증 대상 자체를 목으로 만들면 그 테스트는 아무것도 검증하지 않는다 —
  리뷰에서 가장 흔히 걸리는 실패 유형이다.
- 테스트는 서로 독립이고 실행 순서에 의존하지 않는다. 공통 준비는 프로젝트 관례의 픽스처 위치에 둔다.
- **커버리지는 실행된 줄을 센다, 검증된 동작이 아니다.** 단정이 없는 테스트는 커버리지 0과 같다.

## 체크리스트

- [ ] 검증 계획의 시나리오 ID 마다 대응하는 테스트가 있는가
- [ ] 각 테스트가 **실패해야 할 때 실패하는 것을 확인**했는가
- [ ] 정상 경로 / 오류 경로 / 경계값을 다뤘는가
- [ ] 검증 대상을 목으로 대체하지 않았는가
- [ ] 테스트가 서로 독립인가 (순서 의존 없음)
- [ ] 티어가 소요 시간에 맞는가
- [ ] 검증하지 못한 것을 적어 남겼는가
