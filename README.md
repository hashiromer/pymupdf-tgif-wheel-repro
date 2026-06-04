# PyMuPDF public vs alpha "wheels-tgif" — output divergence at `USE_TGIF=0`

A minimal, self-contained reproduction showing that the **public PyMuPDF wheel**
(PyPI) and the **alpha "wheels-tgif" wheel** produce **different `pymupdf4llm`
output for the same PDFs** — *even when the alpha wheel is forced to its legacy
grid path with `USE_TGIF=0`*, and even though **both report the same version
`1.27.2.3`**.

## Why this repo exists

The two distributions ship the **same version string** but are **different
builds**:

| | Public (PyPI) | Alpha (`wheels-tgif`) |
|---|---|---|
| `pymupdf.__version__` | `1.27.2.3` | `1.27.2.3` (collides) |
| `USE_TGIF` in `pymupdf/table.py` | absent | present |
| extra native lib | — | ships `_tgif.so` |
| table-grid modes | legacy only | `USE_TGIF=0` legacy / `1` TGIFVx / `4` TableGridExtractorV4 |

Because the versions collide, they **cannot coexist** in one environment (a
normal `pip install` may consider the requirement already satisfied and keep the
wrong wheel). So each wheel gets its **own virtual environment**, and this repo
drives both to compare their raw output on identical inputs.

The interesting claim is the last row of the comparison: setting `USE_TGIF=0`
selects the alpha build's *legacy* grid path, which is *supposed* to behave like
the public wheel — but the two still diverge, because the alpha `table.py` and
native binary are simply different code. This repo proves that with concrete
PDFs.

## Layout

```
.
├── pdfs/                  # PDFs that produce different output between the wheels
├── compare.py             # runs raw pymupdf4llm.to_markdown in each venv and diffs (NO normalization)
├── requirements-public.txt
├── requirements-alpha.txt
├── setup.sh               # creates .venv-public and .venv-alpha and verifies the builds differ
└── README.md
```

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) (fast Python env manager).

```bash
./setup.sh
```

This creates two environments and asserts that one has `USE_TGIF` support and
the other does not:

```
.venv-public  -> pymupdf 1.27.2.3  USE_TGIF_support=False
.venv-alpha   -> pymupdf 1.27.2.3  USE_TGIF_support=True
```

<details>
<summary>Plain <code>venv</code> + <code>pip</code> instead of <code>uv</code></summary>

```bash
python3.12 -m venv .venv-public
.venv-public/bin/pip install -r requirements-public.txt

python3.12 -m venv .venv-alpha
.venv-alpha/bin/pip install -r requirements-alpha.txt
```
</details>

## Run the comparison

```bash
# public wheel  vs  alpha wheel @ USE_TGIF=0 (legacy grid), write per-PDF diffs
python compare.py --out-dir diffs
```

What it does, per PDF:

1. runs `pymupdf4llm.to_markdown(pdf, page_chunks=True, table_strategy="lines_strict", dpi=150)`
   in **each** venv (the alpha venv with `USE_TGIF=0` exported before import),
2. takes the **raw** returned string — **no normalization** of any kind,
3. flags the PDF if the two strings are not **byte-identical**, and writes a
   unified diff to `diffs/<pdf>.diff`.

### Try the other grid modes

```bash
python compare.py --use-tgif 1   # alpha TGIFVx
python compare.py --use-tgif 4   # alpha TableGridExtractorV4
```

## Expected result

All 8 PDFs under `pdfs/` differ between the two wheels at `USE_TGIF=0`. Real
divergences observed in `diffs/`:

- **Reading-order change** — identical text, blocks emitted in a different order
  (e.g. `1634690602_page1.pdf`: same 2139 chars, an address block moves relative
  to a picture placeholder).
- **Region classified differently** — the public wheel emits a region as a
  Markdown table, while the alpha legacy wheel wraps the same region as a picture
  with `----- Start of picture text -----` (e.g. `SERFF_CA_page41.pdf`).
- **Different heading detection & picture bounding boxes** — different `##`
  heading promotion and different reported picture sizes, e.g. `p29_page1.pdf`
  shows `picture [80 x 20]` (public) vs `picture [566 x 654]` (alpha) for the
  same image, plus a differently structured table.

This confirms the two wheels are **not interchangeable**: results obtained with
the public wheel cannot be treated as a `USE_TGIF=0` baseline for the alpha
wheel, because the legacy code path itself differs between the builds.

## Notes

- "Raw" output means **upstream of any benchmark normalization** — this isolates
  the wheel behavior itself.
- The PDFs are single-page samples; filenames with spaces/diacritics were
  renamed to ASCII for portability.
