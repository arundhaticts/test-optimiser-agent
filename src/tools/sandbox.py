"""
Isolated sandbox for static validation of generated tests.

MUST CONTAIN:
- validate(test_code) -> {'valid': bool, 'error': str}: syntax + import check in a
  subprocess/container. NEVER executes against production systems.
"""
