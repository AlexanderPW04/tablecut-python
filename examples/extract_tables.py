"""Extract tables from a PDF and print them as markdown.

Usage:
    export TABLECUT_API_KEY=your_key   # or: set TABLECUT_API_KEY=... on Windows
    python examples/extract_tables.py path/to/document.pdf
"""

import sys

from tablecut import RateLimitError, Tablecut, TablecutError


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python examples/extract_tables.py <document.pdf>")
        return 2

    pdf_path = sys.argv[1]
    client = Tablecut()  # reads TABLECUT_API_KEY from the environment

    try:
        result = client.extract(pdf_path, format="json,markdown")
    except RateLimitError as exc:
        wait = f" — retry in {exc.retry_after}s" if exc.retry_after else ""
        print(f"Rate limited ({exc.code}){wait}: {exc.message}")
        return 1
    except TablecutError as exc:
        print(f"Extraction failed: {exc}")
        return 1

    doc = result["document"]
    print(
        f"{doc['filename']}: {len(result['tables'])} table(s) found "
        f"across {doc['pages_processed']} of {doc['page_count']} page(s)\n"
    )

    for table in result["tables"]:
        first, last = table["page_range"]
        pages = f"page {first}" if first == last else f"pages {first}-{last}"
        print(f"--- {table['id']} ({pages}, confidence {table['confidence']:.2f}) ---")
        print(table["markdown"])
        print()

    for warning in result["warnings"]:
        print(f"warning [{warning['code']}]: {warning['message']}")

    usage = result["usage"]
    print(
        f"\nBilled {usage['pages_billed']} page(s) "
        f"({usage['vision_pages']} vision page(s) at "
        f"{usage['vision_page_multiplier']}x) "
        f"in {result['processing_time_ms']} ms"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
