#!/usr/bin/env python3
"""
check_secrets.py — Scan the codebase for hardcoded secrets.

Run manually:    python scripts/check_secrets.py
Run in CI:       python scripts/check_secrets.py  (exits 1 if anything found)

What it catches:
  - Variables named password/secret/api_key/token assigned a non-empty string
  - AWS access key patterns (AKIA...)
  - Private key PEM headers
  - Generic "key = <value>" patterns that look like credentials

What it ignores:
  - Empty string assignments  (password = "")
  - Placeholder strings       (password = "your-password-here", "changeme", etc.)
  - Environment variable reads (os.getenv, os.environ)
  - Type annotations          (password: str)
  - Test files                (test_*.py) — test fixtures use dummy values by design
  - This script itself
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# ── Patterns that suggest a hardcoded secret ──────────────────────────────────

# Matches: password = "something", secret_key = 'abc123', api_key = "sk-live-..."
_CREDENTIAL_ASSIGN = re.compile(
    r'(?i)(password|secret|api_key|apikey|token|auth_key|private_key|access_key)\s*=\s*["\'](.+?)["\']'
)

# AWS access key IDs always start with AKIA
_AWS_KEY = re.compile(r'AKIA[0-9A-Z]{16}')

# PEM private key header
_PEM_HEADER = re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----')

# ── Values that are definitely NOT secrets ────────────────────────────────────

_SAFE_VALUES = {
    "",
    "your-password-here",
    "your-secret-here",
    "changeme",
    "change-me",
    "placeholder",
    "example",
    "your-api-key",
    "your_api_key",
    "xxx",
    "...",
    "<your-secret>",
    "secret",         # bare word used as a field name in tests
    "password",       # bare word used as a field name in tests
    "token",          # bare word used as a field name in tests
}

_SAFE_VALUE_PREFIXES = (
    "your-",
    "your_",
    "<",
    "${",
    "%(",
    "env(",
)

_SAFE_LINES = (
    "os.getenv",
    "os.environ",
    "getenv(",
    ".env",
    "field_validator",
    "description=",
    ": str",
    ": Optional",
    "# ",          # comment lines — allow documentation examples
)


def _is_safe_value(value: str) -> bool:
    v = value.strip().lower()
    if v in _SAFE_VALUES:
        return True
    if any(v.startswith(p) for p in _SAFE_VALUE_PREFIXES):
        return True
    # Very short values are more likely to be field names than real secrets
    if len(v) <= 3:
        return True
    return False


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, line) pairs that look like hardcoded secrets."""
    findings: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()

        # Skip blank lines and pure comments
        if not stripped or stripped.startswith("#"):
            continue

        # Skip lines that are clearly safe patterns
        if any(safe in line for safe in _SAFE_LINES):
            continue

        # Check credential assignment pattern
        for match in _CREDENTIAL_ASSIGN.finditer(line):
            value = match.group(2)
            if not _is_safe_value(value):
                findings.append((lineno, line.rstrip()))
                break

        # Check AWS key pattern
        if _AWS_KEY.search(line):
            findings.append((lineno, line.rstrip()))

        # Check PEM header
        if _PEM_HEADER.search(line):
            findings.append((lineno, line.rstrip()))

    return findings


def main() -> int:
    repo_root = Path(__file__).parent.parent

    # Files to scan: all .py files except this script and test files
    scan_files = [
        p for p in repo_root.rglob("*.py")
        if p.name != "check_secrets.py"
        and not p.name.startswith("test_")
        and ".git" not in p.parts
        and "__pycache__" not in p.parts
        and ".venv" not in p.parts
        and "venv" not in p.parts
        and "site-packages" not in p.parts
    ]

    total_findings: list[tuple[Path, int, str]] = []

    for path in sorted(scan_files):
        findings = _scan_file(path)
        for lineno, line in findings:
            total_findings.append((path.relative_to(repo_root), lineno, line))

    if not total_findings:
        print("✓ Secret scan passed — no hardcoded credentials found.")
        return 0

    print(f"✗ Secret scan FAILED — {len(total_findings)} potential secret(s) found:\n")
    for file_path, lineno, line in total_findings:
        print(f"  {file_path}:{lineno}")
        print(f"    {line[:120]}")
        print()

    print("Fix: move any real secrets to .env and read them with os.getenv().")
    print("If this is a false positive, add the value to _SAFE_VALUES in check_secrets.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
