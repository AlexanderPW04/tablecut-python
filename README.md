# tablecut-python

Python client for [Tablecut](https://tablecut.com) — extract tables from PDFs
as clean JSON, markdown, or CSV. Handles merged cells, multi-page tables, and
scanned documents, with per-table confidence scores.

## Install

```bash
pip install requests
```

Drop [`tablecut.py`](tablecut.py) into your project (single file, one
dependency). Get an API key at [tablecut.com](https://tablecut.com), or
subscribe on [RapidAPI](https://rapidapi.com/piealex/api/tablecut-pdf-table-extraction-api).

## Quickstart

```python
from tablecut import Tablecut

client = Tablecut()  # reads TABLECUT_API_KEY
result = client.extract('report.pdf', format='json,markdown')
for table in result['tables']:
    print(table['markdown'])
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

- `headers` is `null` when no header row was detected.
- `rows` has merged cells resolved; original geometry is in `spans`. Empty
  cells are `null`.
- Vision-fallback pages (scanned documents) bill at 3x, reported in `usage`.
- A PDF with no tables is a success: empty `tables`, explanatory `warnings`.

## Options

```python
result = client.extract(
    'report.pdf',          # path, bytes, or an open binary file
    pages='1,3,5-10',      # 1-indexed pages and ranges; default 'all'
    format='json,markdown' # any of json, markdown, csv; default 'json'
)
```

## Errors

Every error carries a stable `code`, the HTTP `status_code`, and a
`request_id` for support.

```python
from tablecut import AuthenticationError, InvalidRequestError, RateLimitError, ServerError

try:
    result = client.extract('report.pdf')
except RateLimitError as exc:      # 429: rate_limited or quota_exceeded
    print(exc.code, exc.retry_after)
except InvalidRequestError as exc: # 4xx: file_too_large, invalid_pages, ...
    print(exc.code)
except AuthenticationError:        # 401
    ...
except ServerError:                # 5xx
    ...
```

## Example

```bash
python examples/extract_tables.py path/to/document.pdf
```

## Links

- Website and API keys: [tablecut.com](https://tablecut.com)
- API reference: [tablecut.com/docs-public](https://tablecut.com/docs-public)
- RapidAPI listing: [rapidapi.com/piealex/api/tablecut-pdf-table-extraction-api](https://rapidapi.com/piealex/api/tablecut-pdf-table-extraction-api)

## License

[MIT](LICENSE)
