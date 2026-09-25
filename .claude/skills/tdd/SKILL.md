---
name: tdd
description: Implement features using Test-Driven Development (TDD) with Red-Green-Refactor cycle.
disable-model-invocation: true
---

# Test-Driven Development

Implement $ARGUMENTS using Test-Driven Development (TDD).

## TDD Cycle

```
Repeat: Red → Green → Refactor

1. Red:    Write a failing test
2. Green:  Write minimal code to pass the test
3. Refactor: Clean up code (tests still pass)
```

## Implementation Steps

### Phase 1: Test Design

1. **Confirm Requirements**
   - What is the input
   - What is the output
   - What are the edge cases

2. **List Test Cases**
   ```
   - [ ] Happy path: Basic functionality
   - [ ] Happy path: Boundary values
   - [ ] Error case: Invalid input
   - [ ] Error case: Error handling
   ```

### Phase 2: Red-Green-Refactor

#### Step 1: Write First Test (Red)

```python
# tests/test_{module}.py
def test_{function}_basic():
    """Test the most basic case"""
    result = function(input)
    assert result == expected
```

Run test and **confirm failure**:
```bash
{TEST_ONE}   # 이 템플릿 기본값: uv run pytest tests/test_{module}.py -v
```

#### Step 2: Implementation (Green)

Write **minimal** code to pass the test:
- Don't aim for perfection
- Hardcoding is OK
- Just make the test pass

Run test and **confirm success**:
```bash
{TEST_ONE}   # 이 템플릿 기본값: uv run pytest tests/test_{module}.py -v
```

#### Step 3: Refactoring (Refactor)

Improve while tests still pass:
- Remove duplication
- Improve naming
- Clean up structure

```bash
{TEST_ONE}   # Confirm still passes (템플릿 기본값: uv run pytest tests/test_{module}.py -v)
```

#### Step 4: Next Test

Return to Step 1 with next test case from the list.

### Phase 3: Completion Check

```bash
# Run all tests
{TEST_ALL}   # 이 템플릿 기본값: uv run pytest -v

# Check coverage (target 80%+), when the project measures it
{TEST_COVERAGE}   # 이 템플릿 기본값: uv run pytest --cov={module} --cov-report=term-missing
```

## 명령어 치환 (stack-agnostic)

`{TEST_ONE}` / `{TEST_ALL}` / `{TEST_COVERAGE}` 는 자리표시자다. 실제 명령은
`CLAUDE.md` 의 `공통 명령어` 블록에서 읽는다. `/initproject` 가 그 블록을 이
프로젝트의 실제 명령으로 채워 두었다.

Red-Green-Refactor 가 성립하지 않는 스택도 있다. 예를 들어 Yocto recipe
유지보수에서는 단위 테스트가 없고 `bitbake -p` 파싱 검사와 `ptest`/`oeqa`
런타임 테스트가 그 자리를 대신한다. 그 경우 **실패를 먼저 재현**한다는 원칙만
유지하고 명령은 프로젝트 것을 쓴다.

## Report Format

```markdown
## TDD Complete: {Feature Name}

### Test Cases
- [x] {test1}: {description}
- [x] {test2}: {description}
...

### Coverage
{Coverage report}

### Implementation Files
- `src/{module}.py`: {description}
- `tests/test_{module}.py`: {N} tests
```

## Notes

- Write tests **first** (not after)
- Keep each cycle **small**
- Refactor **after** tests pass
- Prioritize **working code** over perfection
