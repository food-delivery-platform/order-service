"""Package Lambda function code + runtime dependencies into deployment zips.

For each function in DEPLOYABLE, creates build/<name>.zip containing:
  - the entire src/ tree (so imports like src.lambdas.<name>.handler resolve), and
  - all runtime dependencies from requirements-lambda.txt, installed once into
    build/deps and placed at the zip root so `import pydantic` works on Lambda.

Dependencies are installed with Lambda-compatible wheels (manylinux2014 x86_64,
cpython 3.12) so the archive is valid regardless of the OS this script runs on.

Usage:
    python scripts/package_lambdas.py                         # package all
    python scripts/package_lambdas.py create_payment_session  # single lambda
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
BUILD_DIR = PROJECT_ROOT / "build"
DEPS_DIR = BUILD_DIR / "deps"
REQUIREMENTS = PROJECT_ROOT / "requirements-lambda.txt"

# Lambda runtime target (create-function uses python3.12 on x86_64 by default).
LAMBDA_PYTHON_VERSION = "3.12"
LAMBDA_PLATFORM = "manylinux2014_x86_64"

DEPLOYABLE = [
    "validate_order",
    "resolve_delivery_address",
    "create_order_step",
    "create_payment_session",
    "paypal_webhook",
    "verify_payment",
    "mark_payment_result",
    "publish_order_event",
]

EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pyd"}


def _should_exclude(path: Path) -> bool:
    """Return True if *path* should be excluded from the zip."""
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    for part in path.parts:
        if part.startswith(".") or part == "__pycache__":
            return True
    return False


def install_dependencies() -> None:
    """Install runtime deps into DEPS_DIR with Lambda-compatible wheels."""
    if DEPS_DIR.exists():
        shutil.rmtree(DEPS_DIR)

    DEPS_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(DEPS_DIR),
        "--platform",
        LAMBDA_PLATFORM,
        "--python-version",
        LAMBDA_PYTHON_VERSION,
        "--only-binary=:all:",
        "--requirement",
        str(REQUIREMENTS),
    ]
    print(f"  installing deps: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _add_tree(zf: zipfile.ZipFile, root: Path, relative_to: Path) -> None:
    """Add all files under *root* to zip, with arcnames relative to *relative_to*."""
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        if _should_exclude(file):
            continue
        arcname = str(file.relative_to(relative_to))
        zf.write(file, arcname)


def package_lambda(name: str) -> Path:
    """Create build/<name>.zip with src/ tree + runtime dependencies.

    Returns:
        Path to the created zip file.
    """
    BUILD_DIR.mkdir(exist_ok=True)
    zip_path = BUILD_DIR / f"{name}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_tree(zf, SRC_DIR, PROJECT_ROOT)
        _add_tree(zf, DEPS_DIR, DEPS_DIR)

    print(f"  {name}  ->  {zip_path}  ({zip_path.stat().st_size // 1024} KB)")
    return zip_path


def main() -> None:
    targets = sys.argv[1:] if len(sys.argv) > 1 else DEPLOYABLE

    for t in targets:
        if t not in DEPLOYABLE:
            print(f"Unknown lambda: {t} (allowed: {DEPLOYABLE})", file=sys.stderr)
            sys.exit(1)

    print(f"Packaging {len(targets)} lambda(s) into {BUILD_DIR}/ ...")

    install_dependencies()

    for name in targets:
        try:
            package_lambda(name)
        except Exception:
            print(f"Failed to package {name}", file=sys.stderr)
            raise

    print("\nDone.")


if __name__ == "__main__":
    main()
