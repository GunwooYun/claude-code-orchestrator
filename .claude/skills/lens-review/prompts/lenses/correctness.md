Look ONLY for correctness defects — cases where the code does something other
than what it evidently intends.

Consider:
- Boundary values: empty, zero, one, maximum, negative, overflow
- Inputs that are absent, malformed, duplicated or out of order
- Error paths: values that are ignored, exceptions that escape or are swallowed,
  partial writes, operations not undone after a failure half-way
- State and lifetime: use after release, double release, references that
  outlive what they point at, shared mutable state
- Concurrency: races, ordering assumptions, non-atomic read-modify-write,
  reentrancy, signal and interrupt safety
- Return values and status codes that callers do not check
- Off-by-one in ranges, indices, slicing, retry and timeout counts
- Type or unit confusion: seconds and milliseconds, bytes and characters,
  0-based and 1-based, text encodings, path separators

For each finding, give the exact input or state that triggers it.
