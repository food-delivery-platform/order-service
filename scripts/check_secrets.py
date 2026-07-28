"""Fail the build when a likely credential is committed to the repository.

Run locally:  python scripts/check_secrets.py
CI runs the same command; a non-zero exit code blocks the pull request.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKIPPED_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico", ".svg", ".lock"}
)

SKIPPED_PATHS = frozenset({"scripts/check_secrets.py", "tests/test_check_secrets.py"})

PLACEHOLDER_MARKERS = (
    "${",
    "os.environ",
    "getenv",
    "example",
    "changeme",
    "placeholder",
    "redacted",
    "xxxx",
    "your-",
    "dummy",
    "***",
)

ALLOW_MARKER = "secret-scan: allow"

RULES = (
    (
        "aws-access-key-id",
        re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])"),
    ),
    (
        "database-url-with-password",
        re.compile(r"postgres(?:ql)?(?:\+[a-z0-9]+)?://[^\s:/@\"']+:[^\s@/\"']+@"),
    ),
    (
        "json-web-token",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    (
        "hardcoded-credential",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\b"
            r"\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"
        ),
    ),
)


def tracked_files() -> list[Path]:
    """Return every file that Git knows about, as paths relative to REPO_ROOT.

    Uses ``git ls-files -z`` so filenames with spaces or special characters
    are handled correctly.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True,
        text=False,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(
            "check_secrets: git ls-files failed; refusing to scan partial set",
            file=sys.stderr,
        )
        sys.exit(2)

    raw = result.stdout.split(b"\0")
    return [REPO_ROOT / p.decode("utf-8") for p in raw if p]


def is_scannable(path: Path) -> bool:
    """Return True for text-like files the scanner should inspect."""
    if path.suffix.lower() in SKIPPED_SUFFIXES:
        return False

    rel = path.resolve().relative_to(REPO_ROOT.resolve())
    if str(rel.as_posix()) in SKIPPED_PATHS:
        return False

    if not path.is_file():
        return False

    return path.stat().st_size != 0


def looks_like_placeholder(line: str) -> bool:
    """Return True when *line* contains a known placeholder marker."""
    lower = line.lower()
    return any(marker.lower() in lower for marker in PLACEHOLDER_MARKERS)


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """Scan *text* line by line and return a list of (line_no, rule_name, line)."""
    findings: list[tuple[int, str, str]] = []

    for idx, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        if looks_like_placeholder(line):
            continue

        for rule_name, pattern in RULES:
            if pattern.search(line):
                findings.append((idx, rule_name, line.strip()))
                break  # one finding per line is enough

    return findings


def main() -> int:
    exit_code = 0
    any_file_scanned = False

    for path in tracked_files():
        if not is_scannable(path):
            continue
        any_file_scanned = True

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        findings = scan_text(text)
        if not findings:
            continue

        print(f"\n{path.relative_to(REPO_ROOT)} — {len(findings)} finding(s):")
        for line_no, rule_name, snippet in findings:
            print(f"  line {line_no}: [{rule_name}] → {snippet}")
        exit_code = 1

    if not any_file_scanned:
        print("check_secrets: no tracked files were scanned", file=sys.stderr)
        return 1

    if exit_code == 0:
        print("check_secrets: no credentials found")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
