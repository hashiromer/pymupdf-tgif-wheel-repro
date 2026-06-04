#!/usr/bin/env bash
# Create the two isolated environments for the reproduction:
#
#   .venv-public  -> public PyMuPDF wheel from PyPI
#   .venv-alpha   -> the 3 private "wheels-tgif" alpha wheels
#
# They report the same version (1.27.2.3) but are different builds and CANNOT
# coexist in one environment, which is exactly why each gets its own venv.
#
# Requires `uv` (https://docs.astral.sh/uv/). If you prefer plain venv+pip, the
# equivalent commands are shown in the README.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

echo "==> [1/2] Public env (.venv-public)"
uv venv .venv-public --python "$PYTHON_VERSION"
VIRTUAL_ENV=.venv-public uv pip install -r requirements-public.txt

echo "==> [2/2] Alpha env (.venv-alpha)"
uv venv .venv-alpha --python "$PYTHON_VERSION"
VIRTUAL_ENV=.venv-alpha uv pip install -r requirements-alpha.txt

echo
echo "==> Verifying the two builds are actually different"

.venv-public/bin/python - <<'PY'
import pathlib, pymupdf
t = pathlib.Path(pymupdf.__file__).parent / "table.py"
has = "USE_TGIF" in t.read_text(errors="ignore")
print(f"  public: pymupdf {pymupdf.__version__}  USE_TGIF_support={has}")
assert not has, "PUBLIC env unexpectedly has USE_TGIF support — wrong wheel installed."
PY

.venv-alpha/bin/python - <<'PY'
import pathlib, pymupdf
t = pathlib.Path(pymupdf.__file__).parent / "table.py"
has = "USE_TGIF" in t.read_text(errors="ignore")
print(f"  alpha : pymupdf {pymupdf.__version__}  USE_TGIF_support={has}")
assert has, (
    "ALPHA env is MISSING USE_TGIF support — the public PyPI wheel got installed "
    "instead of the alpha wheel (version collision). Wipe .venv-alpha and retry."
)
PY

echo
echo "Both environments ready. Now run:"
echo "  python compare.py --out-dir diffs"
