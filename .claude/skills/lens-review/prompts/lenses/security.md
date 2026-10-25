Look ONLY for security defects.

Consider:
- Untrusted input reaching a sensitive operation: shell, query, path,
  deserialization, template, redirect target
- Command construction by string concatenation instead of argument arrays
- Path traversal, symlink following, unsafe temporary files, TOCTOU
- Secrets: hardcoded values, secrets in logs, in error messages, in process
  arguments, in files with permissive modes
- Authentication and authorization: checks that can be skipped, ordering that
  grants access before validation, flags read from the wrong place
- Fallbacks weaker than the primary path, especially ones an attacker can force
  by making the primary path fail
- Defaults that are permissive when a value is missing or unparsable
- Comparison of secrets with non-constant-time equality
- Resource exhaustion: unbounded reads, allocation sized by untrusted input,
  missing timeouts
- Error messages that reveal whether an identifier exists

State who the attacker is and what they gain. A finding that needs privileges
the attacker already has is not a finding — say so instead.
