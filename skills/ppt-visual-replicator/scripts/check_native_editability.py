#!/usr/bin/env python3
"""Decide whether a PPTX should be preserved instead of reconstructed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def assess_native_editability(target: str | Path, target_slide: int | None = None) -> dict[str, Any]:
    """Return a conservative native-editability decision for a target deck.

    A source is preservable only when every selected slide contains native
    editable content and none is an image-only slide.  This intentionally does
    not claim that every decoration is editable; it answers the narrower,
    safety-critical question of whether a visual-replication pass would be
    needless and lossy.
    """

    ledger = inspect_pptx(target)
    selected = [
        slide
        for slide in ledger["slides"]
        if target_slide is None or int(slide["slide_number"]) == target_slide
    ]
    if not selected:
        raise InputError(f"target slide does not exist: {target_slide}")

    pages = []
    for slide in selected:
        native_text_chars = int(slide.get("text_chars", 0))
        table_count = int(slide.get("table_count", 0))
        chart_count = int(slide.get("chart_count", 0))
        graphic_frame_count = int(slide.get("graphic_frame_count", 0))
        picture_count = int(slide.get("picture_count", 0))
        native_content = bool(
            native_text_chars or table_count or chart_count or graphic_frame_count
        )
        image_only = bool(
            picture_count == 1
            and not native_content
            and table_count == 0
            and chart_count == 0
        )
        preservable = native_content and not image_only
        pages.append(
            {
                "slide_number": int(slide["slide_number"]),
                "preservable": preservable,
                "native_text_chars": native_text_chars,
                "picture_count": picture_count,
                "table_count": table_count,
                "chart_count": chart_count,
                "graphic_frame_count": graphic_frame_count,
                "reason": (
                    "contains native editable content"
                    if preservable
                    else "image-only or no native editable content"
                ),
            }
        )

    preserve_recommended = all(page["preservable"] for page in pages)
    return {
        "schema": "ppt_visual_native_editability.v1",
        "target_pptx": ledger["path"],
        "target_sha256": ledger["sha256"],
        "selected_slide_numbers": [page["slide_number"] for page in pages],
        "selected_slide_count": len(pages),
        "preserve_recommended": preserve_recommended,
        "reason": (
            "All selected slides already contain native editable content; preserve the source to avoid a lossy redraw."
            if preserve_recommended
            else "Reconstruction remains necessary because at least one selected slide is image-only/non-native."
        ),
        "slides": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether a target PPTX is already safe to preserve as an editable delivery."
    )
    parser.add_argument("--target", required=True)
    parser.add_argument("--target-slide", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()
    try:
        result = assess_native_editability(args.target, args.target_slide)
    except InputError as exc:
        raise SystemExit(str(exc)) from exc
    if args.out:
        _write_json(Path(args.out).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
