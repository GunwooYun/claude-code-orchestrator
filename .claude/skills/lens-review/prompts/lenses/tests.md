Look ONLY at whether the change is actually verified.

Consider:
- New or changed behaviour that no test exercises
- Tests that cannot fail: no assertion, an assertion on a constant, matchers so
  broad that any result passes, conditions that accept either outcome
- Tests that ignore the result of what they run (exit code, output, exception)
- Tests that verify a reimplementation of the logic rather than the real code
- Fixtures or mocks that hide the behaviour under test
- Tests that change shared state (environment variables, files, globals) and do
  not restore it
- Missing boundary and error cases when the happy path is covered
- Tests that depend on execution order, wall-clock time, network or platform
- Assertions that would still pass if the defect the test exists to catch were
  put back

For each finding, name the test and the change to the code under test that it
would fail to catch. Do not ask for tests of code the change did not touch.
