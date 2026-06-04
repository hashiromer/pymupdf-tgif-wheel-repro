#!/usr/bin/env python3
"""Reproduce: the public PyMuPDF wheel and the alpha "wheels-tgif" wheel
produce DIFFERENT raw pymupdf4llm output for the same PDFs — even when the
alpha wheel is forced to its legacy grid path with USE_TGIF=0.

The two wheels report the same version (1.27.2.3) but are different builds and
cannot coexist in one environment, so this script drives each from its own venv:

    .venv-public  -> public PyPI wheel        (no USE_TGIF support)
    .venv-alpha   -> alpha wheels-tgif wheel   (USE_TGIF selects the grid mode)

"Raw" = the exact string returned by ``pymupdf4llm.to_markdown`` with NO
post-processing (no pipe->HTML table conversion, no whitespace/cell
normalization). Two outputs count as different iff they are not byte-identical.

Usage
-----
    python compare.py                       # public vs alpha@USE_TGIF=0, summary
    python compare.py --out-dir diffs       # also write per-PDF unified diffs
    python compare.py --use-tgif 1          # compare against alpha grid mode 1
    python compare.py --pdf-dir pdfs        # point at a different PDF folder

`extract` is an internal per-venv worker; you normally don't call it directly.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _pdfs(pdf_dir: str) -> list[str]:
    return sorted(str(p) for p in Path(pdf_dir).glob("*.pdf"))


def _raw_markdown(pdf: str, table_strategy: str, dpi: int) -> str:
    import pymupdf4llm  # imported AFTER USE_TGIF is set in the environment

    chunks = pymupdf4llm.to_markdown(
        pdf, page_chunks=True, table_strategy=table_strategy, dpi=dpi
    )
    return "\n\n".join(c.get("text", "") for c in chunks)


def cmd_extract(args: argparse.Namespace) -> int:
    """Runs inside ONE venv: dump {pdf_name: raw_markdown} to JSON."""
    os.environ["USE_TGIF"] = str(args.use_tgif)  # public wheel ignores this
    import pymupdf  # report which build is actually loaded

    table_py = Path(pymupdf.__file__).parent / "table.py"
    has_tgif = "USE_TGIF" in table_py.read_text(encoding="utf-8", errors="ignore")
    out = {
        "_meta": {
            "pymupdf_version": pymupdf.__version__,
            "pymupdf_file": pymupdf.__file__,
            "has_USE_TGIF_support": has_tgif,
            "USE_TGIF_env": os.environ["USE_TGIF"],
        }
    }
    for pdf in _pdfs(args.pdf_dir):
        name = Path(pdf).name
        try:
            out[name] = _raw_markdown(pdf, args.table_strategy, args.dpi)
        except Exception as e:  # noqa: BLE001
            out[name] = f"<<EXTRACT_ERROR:{type(e).__name__}:{e}>>"
    Path(args.out).write_text(json.dumps(out), encoding="utf-8")
    return 0


def _extract_via(python: str, use_tgif: int, args: argparse.Namespace, out: str) -> None:
    cmd = [
        python, str(HERE / "compare.py"), "extract",
        "--use-tgif", str(use_tgif), "--out", out,
        "--pdf-dir", args.pdf_dir,
        "--table-strategy", args.table_strategy, "--dpi", str(args.dpi),
    ]
    subprocess.run(cmd, check=True)


def cmd_diff(args: argparse.Namespace) -> int:
    pub_py = HERE / args.public_python
    alpha_py = HERE / args.alpha_python
    for label, py in (("public", pub_py), ("alpha", alpha_py)):
        if not py.exists():
            sys.exit(f"{label} python not found: {py}\nRun ./setup.sh first.")

    with tempfile.TemporaryDirectory() as td:
        pub_json, alpha_json = f"{td}/public.json", f"{td}/alpha.json"
        print(f"[1/2] public wheel  ({pub_py})  USE_TGIF ignored ...")
        _extract_via(str(pub_py), 0, args, pub_json)
        print(f"[2/2] alpha wheel   ({alpha_py})  USE_TGIF={args.use_tgif} ...")
        _extract_via(str(alpha_py), args.use_tgif, args, alpha_json)
        pub = json.loads(Path(pub_json).read_text())
        alpha = json.loads(Path(alpha_json).read_text())

    pub_meta, alpha_meta = pub.pop("_meta"), alpha.pop("_meta")
    print("\n--- wheels loaded ---")
    print(f"  public: v{pub_meta['pymupdf_version']}  USE_TGIF_support={pub_meta['has_USE_TGIF_support']}")
    print(f"  alpha : v{alpha_meta['pymupdf_version']}  USE_TGIF_support={alpha_meta['has_USE_TGIF_support']}"
          f"  USE_TGIF={alpha_meta['USE_TGIF_env']}")

    common = sorted(set(pub) & set(alpha))
    differ = [n for n in common if pub[n] != alpha[n]]

    out_dir = HERE / args.out_dir if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nPDFs compared : {len(common)}")
    print(f"DIFFER        : {len(differ)}")
    print(f"identical     : {len(common) - len(differ)}\n")
    for name in differ:
        print(f"  DIFFER  {name[:50]:50} public={len(pub[name])}  alpha@tgif{args.use_tgif}={len(alpha[name])}")
        if out_dir:
            ud = difflib.unified_diff(
                pub[name].splitlines(), alpha[name].splitlines(),
                fromfile=f"{name} [PUBLIC v{pub_meta['pymupdf_version']}]",
                tofile=f"{name} [ALPHA v{alpha_meta['pymupdf_version']} USE_TGIF={args.use_tgif}]",
                lineterm="",
            )
            (out_dir / f"{name}.diff").write_text("\n".join(ud), encoding="utf-8")

    if out_dir and differ:
        print(f"\nPer-PDF unified diffs written to: {out_dir}/")
    if not differ:
        print("No byte differences found.")
    else:
        print(f"\nCONCLUSION: {len(differ)} PDF(s) produce different raw output between the two "
              f"wheels even though the alpha wheel ran with USE_TGIF={args.use_tgif} "
              "and both report the same version. The wheels are not interchangeable.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command")

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--pdf-dir", default="pdfs")
        sp.add_argument("--table-strategy", default="lines_strict")
        sp.add_argument("--dpi", type=int, default=150)
        sp.add_argument("--use-tgif", type=int, default=0,
                        help="alpha grid mode: 0 legacy, 1 TGIFVx, 4 TableGridExtractorV4")

    ex = sub.add_parser("extract", help="(internal) dump raw markdown from the current venv")
    common(ex)
    ex.add_argument("--out", required=True)
    ex.set_defaults(func=cmd_extract)

    common(p)
    p.add_argument("--public-python", default=".venv-public/bin/python")
    p.add_argument("--alpha-python", default=".venv-alpha/bin/python")
    p.add_argument("--out-dir", default=None, help="write per-PDF unified diffs here")
    p.set_defaults(func=cmd_diff)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
