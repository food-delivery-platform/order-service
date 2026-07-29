"""Unit tests for the repository secret scanner."""

from __future__ import annotations

import textwrap

from scripts.check_secrets import looks_like_placeholder, scan_text


def test_detects_aws_access_key_id() -> None:
    """A raw AWS access key ID in source code is flagged."""
    text = 'AWS_ACCESS_KEY_ID = "AKIA1234567890ABCDEF"\n'
    findings = scan_text(text)
    assert len(findings) == 1
    assert findings[0][1] == "aws-access-key-id"


def test_detects_database_url_with_password() -> None:
    """A PostgreSQL connection string that carries a password is flagged."""
    text = 'DATABASE_URL = "postgresql://user:pass@host:5432/db"\n'
    findings = scan_text(text)
    assert len(findings) == 1
    assert findings[0][1] == "database-url-with-password"


def test_detects_hardcoded_credential_assignment() -> None:
    """Inline ``password = "secret1234"`` style assignments are flagged."""
    text = 'password = "super-secret-password-value"\n'
    findings = scan_text(text)
    assert len(findings) == 1
    assert findings[0][1] == "hardcoded-credential"


def test_reports_the_correct_line_number() -> None:
    """The scanner reports the 1-based line number, not the index."""
    text = textwrap.dedent("""\
        # header comment
        # another comment
        AKIA1234567890ABCDEF
        # trailing comment
    """)
    findings = scan_text(text)
    assert len(findings) == 1
    assert findings[0][0] == 3


def test_ignores_environment_lookups() -> None:
    """Lines that contain ``os.environ`` or ``getenv`` are skipped."""
    text = 'password = os.environ["DB_PASS"]\n'
    findings = scan_text(text)
    assert len(findings) == 0


def test_ignores_documented_placeholders() -> None:
    """Lines with ``<redacted>``, ``changeme`` etc. are not flagged."""
    text = 'api_key = "<redacted>"\n'
    findings = scan_text(text)
    assert len(findings) == 0


def test_ignores_lines_with_an_allow_marker() -> None:
    """A ``secret-scan: allow`` comment suppresses the finding on that line."""
    text = 'DATABASE_URL = "postgresql://u:p@h/db"  # secret-scan: allow\n'
    findings = scan_text(text)
    assert len(findings) == 0


def test_clean_source_produces_no_findings() -> None:
    """Normal Python source with no secrets returns an empty list."""
    text = textwrap.dedent("""\
        def foo() -> int:
            x = 42
            return x + 1
    """)
    findings = scan_text(text)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Additional edge-case coverage
# ---------------------------------------------------------------------------


def test_placeholder_check_is_case_insensitive() -> None:
    """``looks_like_placeholder`` is case-insensitive."""
    assert looks_like_placeholder("SOME CHANGEME HERE") is True
    assert looks_like_placeholder("Some ChangeMe Here") is True


def test_skips_jwt_tokens() -> None:
    """A realistic-looking JWT is flagged by the scanner."""
    # This is a well-known example HS256 JWT — never valid, not a real secret.
    text = (
        "token = "
        '"eyJhbGciOiJIUzI1NiJ9.'
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        'dozjgNryP4J3jVmNHl0w5N_XgL0n3IWj3J_QTVhK3P8"\n'
    )
    findings = scan_text(text)
    assert len(findings) == 1
    assert findings[0][1] == "json-web-token"


def test_empty_text_returns_no_findings() -> None:
    """An empty string scans without error."""
    assert scan_text("") == []


def test_multiple_matches_in_one_text() -> None:
    """Each line that matches is reported individually."""
    text = textwrap.dedent("""\
        AKIA1234567890ABCDEF
        postgresql://a:b@c:5432/d
    """)
    findings = scan_text(text)
    assert len(findings) == 2
    rule_names = {f[1] for f in findings}
    assert rule_names == {"aws-access-key-id", "database-url-with-password"}
