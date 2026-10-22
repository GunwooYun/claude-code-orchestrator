Look ONLY for integration and operational defects — how this change behaves in
the wider system rather than on its own.

Consider:
- Existing callers of anything whose signature, return value, error behaviour
  or timing changed. Search the repository for them.
- Shared code: does the change alter behaviour for other users of the same file
  or module?
- Build and packaging: new sources or assets registered everywhere the build
  requires; new dependencies declared; version constraints
- Configuration: new settings and their defaults, settings documented but not
  read, settings read but not documented, comments that contradict the code
- Documentation and procedures: guides, READMEs, changelogs and instructions
  that now describe something that no longer happens, or that will break once
  this change is merged (a branch name, a path, a command)
- Startup and shutdown order, dependencies that may be unavailable
- Migration and compatibility: existing installations, stored data, leftover
  files or state from the previous version that this change does not handle
- Failure in operation: what an operator sees, whether the failure can be
  diagnosed, whether it degrades into something less safe
- Anything the change makes dead: code, configuration, documentation

Name the specific caller, file, document or installed state affected.
