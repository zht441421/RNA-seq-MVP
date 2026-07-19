from __future__ import annotations

import argparse
import json

from phase_8_6_reference_common import (
    ReferenceDataError,
    fetch_dataset,
    public_datasets,
    select_datasets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch declared Phase 8.6 public reference datasets.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dataset")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()
    if args.list:
        for dataset in public_datasets():
            size = sum(int(item["size_bytes"]) for item in dataset["retrieval"]["artifacts"])
            print(f"{dataset['dataset_id']}\t{dataset['accession']}\t{size} bytes")
        return 0
    try:
        selected = select_datasets(args.dataset, all_datasets=args.all)
        results = [
            result
            for dataset in selected
            for result in fetch_dataset(dataset, dry_run=args.dry_run, cache_only=args.cache_only)
        ]
    except ReferenceDataError as exc:
        print(f"Phase 8.6 retrieval failed: {exc}")
        return 1
    print(json.dumps({"datasets": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
