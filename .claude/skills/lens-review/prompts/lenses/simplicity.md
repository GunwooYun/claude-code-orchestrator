Look ONLY for unnecessary complexity in the changed code.

Consider:
- Logic duplicated from somewhere that already exists in the repository — name
  the existing place
- An abstraction with a single implementation and no second caller in sight
- Branches that cannot be reached, parameters never varied, options never used
- State that is stored but could be derived
- Nesting that an early return would flatten
- Code the change left behind: helpers that are now dead, unused imports,
  stale comments

Do not propose formatting changes, renames for taste, or restructuring that does
not remove something. Every finding must delete code or remove a concept, and
must say what breaks if the suggested removal is applied carelessly.
