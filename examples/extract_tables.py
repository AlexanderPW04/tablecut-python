# Usage: python examples/extract_tables.py <document.pdf>
# Requires TABLECUT_API_KEY in the environment.

import sys

from tablecut import RateLimitError, Tablecut, TablecutError


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: python examples/extract_tables.py <document.pdf>')
        return 2

    client = Tablecut()

    try:
        result = client.extract(sys.argv[1], format='json,markdown')
    except RateLimitError as exc:
        wait = f' — retry in {exc.retry_after}s' if exc.retry_after else ''
        print(f'Rate limited ({exc.code}){wait}: {exc.message}')
        return 1
    except TablecutError as exc:
        print(f'Extraction failed: {exc}')
        return 1

    doc = result['document']
    print(
        f"{doc['filename']}: {len(result['tables'])} table(s) "
        f"across {doc['pages_processed']} of {doc['page_count']} page(s)\n"
    )

    for table in result['tables']:
        first, last = table['page_range']
        pages = f'page {first}' if first == last else f'pages {first}-{last}'
        print(f"--- {table['id']} ({pages}, confidence {table['confidence']:.2f}) ---")
        print(table['markdown'])
        print()

    for warning in result['warnings']:
        print(f"warning [{warning['code']}]: {warning['message']}")

    usage = result['usage']
    print(
        f"\nBilled {usage['pages_billed']} page(s) "
        f"({usage['vision_pages']} vision at {usage['vision_page_multiplier']}x) "
        f"in {result['processing_time_ms']} ms"
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
