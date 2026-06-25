# CVPR 2026 Paper Markdown Summaries

This folder contains a local pipeline for CVPR 2026 Open Access papers:

- scrape or reuse the CVF paper index
- classify papers into the official CVPR 2026 Call for Papers topic taxonomy
- download PDFs and extract text
- generate one Korean markdown summary per paper with Codex CLI
- prepare selected papers for Zotero import

## Current Data

- Source: <https://openaccess.thecvf.com/CVPR2026?day=all>
- Official topic taxonomy: <https://cvpr.thecvf.com/Conferences/2026/CallForPapers>
- Parsed papers: 4,068
- Index: `data/cvpr2026_index.json`
- Category index: `data/cvpr2026_categories.json`
- Summaries: `summaries/<paper title>.md`
- Zotero import files: `data/zotero/`

## Basic Usage

Refresh the paper index:

```bash
python cvpr2026_summarize.py --scrape
```

Classify papers into official CVPR 2026 categories with Codex CLI:

```bash
python cvpr2026_summarize.py --classify-categories --all --sleep 0.5
```

Use the fast keyword fallback instead of Codex classification:

```bash
python cvpr2026_summarize.py --classify-categories --category-classifier keywords --all
```

List category counts:

```bash
python cvpr2026_summarize.py --list-categories
```

The first column is the zero-based category index. You can pass selected categories by index:

```bash
python cvpr2026_summarize.py --summarize --categories "34,35" --all --sleep 0.5
```

Summarize the first 5 papers:

```bash
python cvpr2026_summarize.py --summarize --limit 5
```

Summarize only selected categories:

```bash
python cvpr2026_summarize.py --summarize --categories "34,35" --all --sleep 0.5
```

Existing markdown files are skipped by default. Add `--overwrite` to regenerate them.

Set a Codex model with `CODEX_MODEL` or `--model`:

```bash
CODEX_MODEL=gpt-5.5 python cvpr2026_summarize.py --summarize --limit 5
python cvpr2026_summarize.py --summarize --limit 5 --model gpt-5.5
```

## Zotero Workflow

The Zotero bridge writes category-specific import files such as:

```text
data/zotero/by_category/Vision + graphics/import.ris
data/zotero/by_category/Vision + graphics/report.json
```

To place papers under a specific Zotero category collection, create or select that collection in Zotero first, then import through `cvpr2026_zotero.py`.

The generated RIS includes paper metadata, category tags, local PDF file attachments when the PDF has been downloaded, and Zotero-readable HTML copies of markdown summaries under `data/zotero/analysis_html/`. The RIS intentionally avoids note fields, so Zotero creates only the paper item plus PDF/HTML child attachments.

Zotero Desktop's local API is read-only, so this script uses Zotero Connector import for writes. Before bulk importing, test with 1-3 papers and confirm Zotero's importer maps the RIS fields the way you want.

## Requirements

- Python 3.10+
- `pdftotext` on PATH for PDF text extraction
- locally authenticated `codex` CLI on PATH for Codex-based classification and summaries
- Zotero Desktop and Zotero Connector local endpoint for Zotero import
- no external Python package required

If `pdftotext` works in one terminal but the script cannot find it, pass the executable path directly:

```bash
python cvpr2026_summarize.py --summarize --categories "16" --limit 1 --pdftotext "C:\Program Files\Git\mingw64\bin\pdftotext.exe"
```

You can also set `PDFTOTEXT` to the same path.

On Windows, if `codex` is installed as `codex.cmd` but Python cannot launch it by name, pass it explicitly:

```bash
python cvpr2026_summarize.py --summarize --categories "16" --limit 1 --pdftotext "C:\Program Files\Git\mingw64\bin\pdftotext.exe" --codex "C:\Users\hungsik\AppData\Roaming\npm\codex.cmd"
```

You can also set `CODEX_CLI` to the same path.

## Zotero Bridge Script

`cvpr2026_zotero.py` is a small wrapper for Zotero-specific operations.

Check Zotero readiness:

```bash
python cvpr2026_zotero.py status --json
```

Check the currently selected Zotero library/collection:

```bash
python cvpr2026_zotero.py selected-target --json
```

Prepare the RIS file for one category:

```bash
python cvpr2026_zotero.py prepare-category 16
```

Import one category into the currently selected Zotero target:

```bash
python cvpr2026_zotero.py import-category 16
```

Test with one item first:

```bash
python cvpr2026_zotero.py import-category 16 --limit 1
```

If you already generated markdown summaries and want Zotero to include readable analysis attachments, regenerate the category import file first:

```bash
python cvpr2026_zotero.py import-category 16 --prepare --limit 1
```

Regenerate the RIS before importing:

```bash
python cvpr2026_zotero.py import-category 16 --prepare
```

Connector RIS import may create items in the library without assigning them to the currently selected collection. Check the import response and Zotero UI after the one-item test before bulk import.

## Output Format

Each paper summary is saved as `summaries/<paper title>.md` and includes:

0. Eight-Line Paper Summary
1. Key Terms & Definitions
2. Motivation & Problem Statement
3. Method & Key Results
4. Conclusion & Impact
