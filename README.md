# tablecut-python

Python client for [Tablecut](https://tablecut.com) — extract tables from PDFs
and get clean JSON, markdown, or CSV back. Handles merged cells, multi-page
tables, and scanned documents, with an honest per-table confidence score.

## Install

```bash
pip install requests
```

Then drop [`tablecut.py`](tablecut.py) into your project (single file, one
dependency). Get an API key at [tablecut.com](https://tablecut.com), or
subscribe on [RapidAPI](https://rapidapi.com/piealex/api/tablecut-pdf-table-extraction-api).

## Quickstart

```python
from tablecut import Tablecut

client = Tablecut()  # reads the TABLECUT_API_KEY environment variable
result = client.extract("report.pdf", format="json,markdown")
for table in result["tables"]:
    print(table["markdown"])
```

## Sample response

```json
{
  "document": { "filename": "report.pdf", "page_count": 42, "pages_processed": 8 },
  "tables": [
    {
      "id": "t1",
      "page_range": [3, 4],
      "extraction_layer": "fast_path",
      "confidence": 0.94,
      "headers": ["Region", "Q1 2026", "Q2 2026"],
      "rows": [
        ["EMEA", "1,204", "1,377"],
        ["APAC", "980", "1,041"]
      ],
      "spans": [{ "row": 0, "col": 1, "rowspan": 1, "colspan": 2 }],
      "markdown": "<!-- pages 3-4 -->\n| Region | Q1 2026 | Q2 2026 |\n| --- | --- | --- |\n| EMEA | 1,204 | 1,377 |\n| APAC | 980 | 1,041 |",
      "notes": ["stitched_across_pages", "merged_cells_resolved"]
    }
  ],
  "warnings": [],
  "usage": { "pages_billed": 10, "vision_pages": 1, "vision_page_multiplier": 3 },
  "processing_time_ms": 843,
  "request_id": "req_8f2c1a"
}
```

Notes on the shape:

- `headers` is `null` when no header row was detected — nothing is guessed.
- `rows` has merged cells **resolved** (values duplicated into every covered
  position); the original merge geometry is preserved in `spans`. Empty cells
  are `null`, not `""`.
- `confidence` is calibrated: ~0.9 means roughly 90% of such tables are fully
  correct.
- Vision-fallback pages (scanned documents) bill at 3x, reported transparently
  in `usage`.
- A PDF with no detectable tables is a **success**: `tables` is empty and
  `warnings` explains why.

## Options

```python
result = client.extract(
    "report.pdf",          # path, bytes, or an open binary file
    pages="1,3,5-10",      # 1-indexed pages and inclusive ranges; default "all"
    format="json,markdown" # any of json, markdown, csv; default "json"
)
```

## Error handling

All API errors carry a stable machine-readable `code` (switch on it — message
wording may change), the HTTP `status_code`, and a `request_id` to include in
support requests.

```python
from tablecut import (
    AuthenticationError,   # 401 — missing or invalid API key
    InvalidRequestError,   # 4xx — bad params, too large, not a PDF, unreadable PDF
    RateLimitError,        # 429 — throttled (retry_after) or monthly quota exhausted
    ServerError,           # 5xx — Tablecut's fault; nothing is billed
    Tablecut,
)

try:
    result = client.extract("report.pdf")
except RateLimitError as exc:
    if exc.code == "quota_exceeded":
        ...  # monthly quota used up — upgrade or wait for the reset
    else:
        ...  # throttled — wait exc.retry_after seconds and retry
except InvalidRequestError as exc:
    print(exc.code)  # e.g. "file_too_large", "invalid_pages", "unprocessable_pdf"
```

## Example

A complete runnable example lives in
[`examples/extract_tables.py`](examples/extract_tables.py):

```bash
python examples/extract_tables.py path/to/document.pdf
```

## Links

- Website & API keys: [tablecut.com](https://tablecut.com)
- API reference: [tablecut.com/docs-public](https://tablecut.com/docs-public)
- RapidAPI listing: [rapidapi.com/piealex/api/tablecut-pdf-table-extraction-api](https://rapidapi.com/piealex/api/tablecut-pdf-table-extraction-api)

## License

[MIT](LICENSE)
