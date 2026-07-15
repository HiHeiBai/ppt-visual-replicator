#!/usr/bin/env python3
"""Record a reviewed full-page imagegen result with immutable image evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_CHECKS = (
    "source_structure_match",
    "no_invented_information_visuals",
    "no_reference_content_transfer",
    "style_contract_match",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write an explicit review record after comparing one generated slide with its source."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--slide", required=True, type=int)
    parser.add_argument("--review-note", required=True)
    parser.add_argument(
        "--accept",
        action="store_true",
        help="Required. By accepting, the reviewer confirms every source, content-firewall, and style check.",
    )
    args = parser.parse_args()

    root = Path(args.run_dir).expanduser().resolve()
    deck = json.loads((root / "deck-run.json").read_text(encoding="utf-8"))
    page = next((item for item in deck.get("pages", []) if int(item["target_slide"]) == args.slide), None)
    if page is None:
        raise SystemExit(f"slide {args.slide} does not exist in this direct run")
    source = root / str(page["source_image"])
    image = root / str(page["generated_image"])
    if not source.is_file() or not source.stat().st_size:
        raise SystemExit(f"slide {args.slide} has no source image to review: {source}")
    if not image.is_file() or not image.stat().st_size:
        raise SystemExit(f"slide {args.slide} has no generated image to review: {image}")
    if not args.accept:
        raise SystemExit("an accepted review requires --accept after a direct visual comparison")
    if not args.review_note.strip():
        raise SystemExit("an accepted review requires a concrete review note")
    checks = {name: True for name in REQUIRED_CHECKS}
    record: dict[str, Any] = {
        "schema": "ppt_visual_generation_review.v1",
        "target_slide": args.slide,
        "accepted": True,
        "generated_image": str(page["generated_image"]),
        "generated_image_sha256": _sha256(image),
        "source_image": str(page["source_image"]),
        "source_image_sha256": _sha256(source),
        "checks": checks,
        "review_note": args.review_note.strip(),
    }
    review_path = root / str(page["run_dir"]) / "generation-review.json"
    _write_json(review_path, record)
    print(json.dumps({"review": str(review_path), "record": record}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
