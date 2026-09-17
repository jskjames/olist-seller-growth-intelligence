"""Download the four publicly mirrored Olist CSVs needed for this case study.

For an authoritative copy, use the two Olist Kaggle dataset pages in README
and place the named CSVs in data/raw instead. Do not commit the raw files.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://raw.githubusercontent.com/dujiaying/olist/master/data/"
FILES = [
    "olist_marketing_qualified_leads_dataset.csv",
    "olist_closed_deals_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
]


def main() -> None:
    dest = ROOT / "data" / "raw"
    dest.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        path = dest / filename
        if path.exists():
            print(f"Already present: {filename}")
            continue
        with urllib.request.urlopen(SOURCE + filename, timeout=90) as response:
            payload = response.read()
        if not payload or not payload.lower().startswith((b"mql_id", b'"order_id"')):
            raise RuntimeError(f"Unexpected source file for {filename}")
        path.write_bytes(payload)
        print(f"Downloaded {filename}: {len(payload):,} bytes, SHA256 {hashlib.sha256(payload).hexdigest()}")
    previous = ROOT / "outputs" / "audit.json"
    if previous.exists():
        expected = json.loads(previous.read_text(encoding="utf-8"))["sha256"]
        for key, filename in zip(("leads", "wins", "orders", "items"), FILES):
            actual = hashlib.sha256((dest / filename).read_bytes()).hexdigest()
            if actual != expected[key]:
                raise RuntimeError(f"The {key} input differs from the audited case study. Review source version.")


if __name__ == "__main__":
    main()
