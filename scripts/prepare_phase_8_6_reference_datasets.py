from __future__ import annotations

import argparse
import json

from phase_8_6_reference_common import (
    ReferenceDataError,
    prepare_dataset,
    public_datasets,
    select_datasets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministically prepare Phase 8.6 reference inputs.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dataset")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.list:
        for dataset in public_datasets():
            print(f"{dataset['dataset_id']}\t{dataset['preprocessing']['adapter']}")
        return 0
    try:
        selected = select_datasets(args.dataset, all_datasets=args.all)
        results = [prepare_dataset(dataset) for dataset in selected]
    except ReferenceDataError as exc:
        print(f"Phase 8.6 preprocessing failed: {exc}")
        return 1
    print(json.dumps({"prepared": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
