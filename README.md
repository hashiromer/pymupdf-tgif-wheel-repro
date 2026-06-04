# `pymupdf4llm` produces different Markdown: public vs private (alpha) build

A minimal, self-contained reproduction showing that **`pymupdf4llm` generates
different Markdown for the same PDFs depending on which build you install** —
the **public** build (PyPI) vs the **private "alpha" / `wheels-tgif`** build —
**even though both report the same version `1.27.2.3`**.

`pymupdf4llm.to_markdown(...)` is the function that produces the Markdown. This
repo calls it on identical PDFs from two isolated environments and shows the raw
output is not byte-identical.

## Why this happens

It is **not** just a runtime flag. The two distributions are genuinely different
code shipped under the same version number, at **both** layers `pymupdf4llm`
uses:

1. **`pymupdf4llm` itself differs** (the pure-Python Markdown layer). The two
   `pymupdf4llm-1.27.2.3-py3-none-any.whl` files have **different SHA-256** and
   different source — e.g. `helpers/utils.py` and `helpers/document_layout.py`
   are not the same between PyPI and the ghostscript index.
2. **The underlying `pymupdf` binary differs.** The alpha `pymupdf` adds
   env-var-selected table-grid extraction (`USE_TGIF`) and ships an extra native
   lib (`_tgif.so`); the public one does not.

| | Public (PyPI) | Alpha (`wheels-tgif`) |
|---|---|---|
| `pymupdf` / `pymupdf4llm` version | `1.27.2.3` | `1.27.2.3` (collides) |
| `pymupdf4llm` wheel SHA-256 | `bd724b79…` | `ba4923a8…` (different code) |
| `USE_TGIF` in `pymupdf/table.py` | absent | present |
| extra native lib | — | ships `_tgif.so` |
| `pymupdf-layout` overlay | — | included |

Because the versions collide, the two builds **cannot coexist** in one
environment (a normal `pip install` may consider the requirement already
satisfied and keep the wrong wheel), so each gets its **own virtual
environment**.

To rule out the objection "it's only the new table-grid mode," `compare.py`
forces the alpha build to its **legacy** grid path with `USE_TGIF=0` and the
Markdown *still* differs — confirming the divergence is the build itself, not a
grid-mode toggle.

## Layout

```
.
├── pdfs/                  # PDFs whose Markdown differs between the two builds
├── compare.py             # runs raw pymupdf4llm.to_markdown in each venv and diffs (NO normalization)
├── requirements-public.txt
├── requirements-alpha.txt
├── setup.sh               # creates .venv-public and .venv-alpha and verifies the builds differ
└── README.md
```

## Where the packages come from

| Environment | Package source | Pinned how |
|---|---|---|
| `.venv-public` | **PyPI** (default index) | `requirements-public.txt` — `pymupdf==1.27.2.3`, `pymupdf4llm==1.27.2.3` |
| `.venv-alpha` | **ghostscript `wheels-tgif` index** | `requirements-alpha.txt` — the 3 wheels by **direct URL + SHA-256** |

The alpha wheels are **not vendored** into this repo (git stays binary-free); they
are downloaded from the ghostscript index at install time and verified against
the recorded SHA-256 hashes. Exact provenance for every platform is in the
[Wheel lineage](#wheel-lineage) table below.

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

All 8 PDFs under `pdfs/` yield different `pymupdf4llm` Markdown between the
public and alpha builds at `USE_TGIF=0`. Real divergences observed in `diffs/`:

- **Reading-order change** — identical text, blocks emitted in a different order
  (e.g. `1634690602_page1.pdf`: same 2139 chars, an address block moves relative
  to a picture placeholder).
- **Region classified differently** — the public build emits a region as a
  Markdown table, while the alpha build wraps the same region as a picture
  with `----- Start of picture text -----` (e.g. `SERFF_CA_page41.pdf`).
- **Different heading detection & picture bounding boxes** — different `##`
  heading promotion and different reported picture sizes, e.g. `p29_page1.pdf`
  shows `picture [80 x 20]` (public) vs `picture [566 x 654]` (alpha) for the
  same image, plus a differently structured table.

This confirms the public and private `pymupdf4llm` builds are **not
interchangeable**: the same `to_markdown()` call yields different Markdown, so
output produced with one build cannot be assumed equal to the other — and it is
not merely a `USE_TGIF` grid-mode effect (the legacy path `USE_TGIF=0` still
differs).

## Wheel lineage

The public wheels come from **PyPI** (`pip install pymupdf==1.27.2.3
pymupdf4llm==1.27.2.3`). The alpha wheels come from the ghostscript
**`wheels-tgif`** index at
`https://ghostscript.com/~julian/wheels-tgif/`. All alpha wheels are version
`1.27.2.3` and were fetched and hashed on 2026-06-04:

| Package | Platform | Wheel (under `https://ghostscript.com/~julian/wheels-tgif/`) | SHA-256 |
|---|---|---|---|
| pymupdf | macOS arm64 | `pymupdf-1.27.2.3-cp310-abi3-macosx_11_0_arm64.whl` | `7edfb64f2cda694fc771809ca568399ec85809ed6e572e73a207305a06f53fc9` |
| pymupdf | Linux x86_64 | `pymupdf-1.27.2.3-cp310-abi3-manylinux_2_28_x86_64.whl` | `aa17a99b47ad5a3a6be3ba8d5d741148acc6933bd9fff9e7cb1fa44b1a8cc1fd` |
| pymupdf | Windows amd64 | `pymupdf-1.27.2.3-cp310-abi3-win_amd64.whl` | `9e7bebb080ae78124a720c08a5dd5a396472b6055eefae39fa75348862e652fb` |
| **pymupdf4llm** | any (pure Python) | `pymupdf4llm-1.27.2.3-py3-none-any.whl` | `ba4923a8827e3d69e398f30fb5233a73d9226f10e261cf7ad5a3116378984db4` |
| pymupdf-layout | macOS arm64 | `pymupdf_layout-1.27.2.3-cp310-abi3-macosx_11_0_arm64.whl` | `e3c36dfacb6aaf2c8a39438c8f312de3e62261590cededf7c9c650776d464a4c` |
| pymupdf-layout | Linux x86_64 | `pymupdf_layout-1.27.2.3-cp310-abi3-manylinux_2_28_x86_64.whl` | `fe548f35fe6ebebe80ebe2771ee95a6a03ef0cd39c348b639e38263f06cb1cef` |
| pymupdf-layout | Windows amd64 | `pymupdf_layout-1.27.2.3-cp310-abi3-win_amd64.whl` | `14cd69b4ad6f702fba5f4cca7a8e20bea7f3d53f4faea2dcf71ddd0f7b1e72bb` |

The alpha `pymupdf4llm` wheel (`ba4923a8…`) is the same pure-Python file across
platforms, **but it is NOT the same as the public PyPI `pymupdf4llm` wheel**
(`bd724b79b…`):

| `pymupdf4llm-1.27.2.3-py3-none-any.whl` | Source | SHA-256 |
|---|---|---|
| public | PyPI (`pip install pymupdf4llm==1.27.2.3`) | `bd724b79fa3f06a5b28d7a65f7acfa8de56e04bdb603ac2d6dff315e0d151aaa` |
| alpha | ghostscript `wheels-tgif` | `ba4923a8827e3d69e398f30fb5233a73d9226f10e261cf7ad5a3116378984db4` |

Same name, same version, different code (e.g. `helpers/utils.py` and
`helpers/document_layout.py` differ). This is a primary reason the Markdown
output differs — independent of the `pymupdf` binary or `USE_TGIF`.

`requirements-alpha.txt` pins the **macOS arm64** rows by `<url>#sha256=<hash>`.
On Linux or Windows, replace the two platform wheels (`pymupdf`,
`pymupdf-layout`) with the matching rows above.

To re-verify a downloaded wheel:

```bash
curl -sO https://ghostscript.com/~julian/wheels-tgif/pymupdf-1.27.2.3-cp310-abi3-macosx_11_0_arm64.whl
shasum -a 256 pymupdf-1.27.2.3-cp310-abi3-macosx_11_0_arm64.whl
```

## Notes

- "Raw" output means **upstream of any benchmark normalization** — this isolates
  the wheel behavior itself.
- The PDFs are single-page samples; filenames with spaces/diacritics were
  renamed to ASCII for portability.
