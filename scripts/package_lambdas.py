"""Package Lambda function code into deployment-ready zip archives.

For each function in the DEPLOYABLE list, creates build/<name>.zip containing
the entire src/ tree so the Lambda runtime can resolve imports like
``src.lambdas.<name>.handler``, ``src.shared.*``, and ``src.modules.*``.

Usage:
    python scripts/package_lambdas.py                # package all
    python scripts/package_lambdas.py create_order_step  # single lambda
"""

import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
BUILD_DIR = PROJECT_ROOT / "build"

DEPLOYABLE = [
    "validate_order",
    "resolve_delivery_address",
    "create_order_step",
    "create_payment_session",  # part 1 (was missing here)
    "paypal_webhook",  # part 2
    "verify_payment",  # part 2
    "mark_payment_result",  # part 2
    "publish_order_event",  # part 2
]

EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pyd"}


def _should_exclude(path: Path) -> bool:
    """Return True if *path* should be excluded from the zip."""
    # Skip compiled bytecode
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    # Skip __pycache__ and hidden directories
    for part in path.parts:
        if part.startswith(".") or part == "__pycache__":
            return True
    return False


def package_lambda(name: str) -> Path:
    """Create build/<name>.zip with the full src/ tree.

    Returns:
        Path to the created zip file.
    """
    BUILD_DIR.mkdir(exist_ok=True)
    zip_path = BUILD_DIR / f"{name}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in SRC_DIR.rglob("*"):
            if not file.is_file():
                continue
            if _should_exclude(file):
                continue
            arcname = str(file.relative_to(PROJECT_ROOT))
            zf.write(file, arcname)

    print(f"  {name}  ->  {zip_path}  ({zip_path.stat().st_size // 1024} KB)")
    return zip_path


def main() -> None:
    targets = sys.argv[1:] if len(sys.argv) > 1 else DEPLOYABLE

    # Validate targets
    for t in targets:
        if t not in DEPLOYABLE:
            print(f"Unknown lambda: {t} (allowed: {DEPLOYABLE})", file=sys.stderr)
            sys.exit(1)

    print(f"Packaging {len(targets)} lambda(s) into {BUILD_DIR}/ ...")
    for name in targets:
        try:
            package_lambda(name)
        except Exception:
            print(f"Failed to package {name}", file=sys.stderr)
            raise

    print("\nDone.")


if __name__ == "__main__":
    main()
