"""Package Lambda artifacts: a shared deps layer + per-function code zips.

Layout:
  - build/layer.zip   -> runtime deps under python/ (a Lambda Layer). Lambda unpacks
                         layers to /opt and /opt/python is on sys.path, so
                         `import pydantic` resolves at runtime.
  - build/<name>.zip   -> ONLY the src/ tree for one function (tiny). Shared deps
                         come from the layer, not from the zip.

Deps use Lambda-compatible wheels (manylinux2014 x86_64, cpython 3.12) so the
artifacts are valid regardless of the OS this script runs on.

Usage:
    python scripts/package_lambdas.py                         # layer + all functions
    python scripts/package_lambdas.py --layer                 # only build the layer
    python scripts/package_lambdas.py create_payment_session  # only that function zip
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
BUILD_DIR = PROJECT_ROOT / "build"
LAYER_DIR = BUILD_DIR / "layer"
LAYER_PYTHON_DIR = LAYER_DIR / "python"
LAYER_ZIP = BUILD_DIR / "layer.zip"
REQUIREMENTS = PROJECT_ROOT / "requirements-lambda.txt"

# Lambda runtime target (functions run python3.12 on x86_64).
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
    """Return True if *path* must be kept out of an artifact."""
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return "__pycache__" in path.parts


def _add_tree(zf: zipfile.ZipFile, root: Path, relative_to: Path) -> None:
    """Add every file under *root* to *zf*, arcnamed relative to *relative_to*."""
    for file in root.rglob("*"):
        if not file.is_file() or _should_exclude(file):
            continue
        zf.write(file, str(file.relative_to(relative_to)))


def _zip_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def build_layer() -> Path:
    """Install runtime deps and zip them as a Lambda layer (build/layer.zip)."""
    if LAYER_DIR.exists():
        shutil.rmtree(LAYER_DIR)
    LAYER_PYTHON_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(LAYER_PYTHON_DIR),
        "--platform",
        LAMBDA_PLATFORM,
        "--implementation",
        "cp",
        "--python-version",
        LAMBDA_PYTHON_VERSION,
        "--only-binary=:all:",
        "--requirement",
        str(REQUIREMENTS),
    ]
    print(f"  installing layer deps: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    if LAYER_ZIP.exists():
        LAYER_ZIP.unlink()
    with zipfile.ZipFile(LAYER_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_tree(zf, LAYER_DIR, LAYER_DIR)

    size_mb = _zip_size_mb(LAYER_ZIP)
    warn = "  <-- WARNING: >50MB, needs S3 upload" if size_mb > 50 else ""
    print(f"  layer -> {LAYER_ZIP} ({size_mb:.1f} MB){warn}")
    return LAYER_ZIP


def package_lambda(name: str) -> Path:
    """Create build/<name>.zip with ONLY the src/ tree (deps come from the layer)."""
    BUILD_DIR.mkdir(exist_ok=True)
    zip_path = BUILD_DIR / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_tree(zf, SRC_DIR, PROJECT_ROOT)

    print(f"  {name} -> {zip_path} ({_zip_size_mb(zip_path):.2f} MB)")
    return zip_path


def main() -> None:
    args = sys.argv[1:]

    if "--layer" in args:
        build_layer()
        return

    targets = args if args else DEPLOYABLE
    for t in targets:
        if t not in DEPLOYABLE:
            print(f"Unknown lambda: {t} (allowed: {DEPLOYABLE})", file=sys.stderr)
            sys.exit(1)

    # No positional names -> full build (layer + every function).
    if not args:
        build_layer()

    print(f"Packaging {len(targets)} lambda(s) into {BUILD_DIR}/ ...")
    for name in targets:
        package_lambda(name)

    print("\nDone.")


if __name__ == "__main__":
    main()
