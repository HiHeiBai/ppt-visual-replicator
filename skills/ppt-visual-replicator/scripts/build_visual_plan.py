#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STRICT_FAMILIES = {"cover", "table", "chart_figure", "ending"}


class PlanError(ValueError):
    pass


def _value(slide: dict[str, Any], key: str) -> int:
    return int(slide.get(key, 0) or 0)


def _score(
    target: dict[str, Any],
    reference: dict[str, Any],
    target_count: int,
    reference_count: int,
) -> tuple[Any, ...]:
    object_difference = sum(
        abs(_value(target, key) - _value(reference, key))
        for key in ("table_count", "picture_count", "chart_count")
    )
    text_difference = abs(_value(target, "text_chars") - _value(reference, "text_chars"))
    target_position = (_value(target, "slide_number") - 1) / max(target_count - 1, 1)
    reference_position = (_value(reference, "slide_number") - 1) / max(reference_count - 1, 1)
    return object_difference, text_difference, abs(target_position - reference_position), _value(reference, "slide_number")


def _reference_page(
    references: list[dict[str, Any]],
    reference_index: int,
    slide_number: int,
) -> dict[str, Any]:
    if reference_index < 0 or reference_index >= len(references):
        raise PlanError(f"reference index does not exist: {reference_index}")
    for slide in references[reference_index].get("slides", []):
        if int(slide.get("slide_number", 0)) == slide_number:
            return slide
    raise PlanError(f"reference slide does not exist: reference {reference_index}, slide {slide_number}")


def build_plan(
    source: dict[str, Any],
    references: list[dict[str, Any]],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not references:
        raise PlanError("at least one reference ledger is required")
    overrides = overrides or {}
    pages = []
    for target in source.get("slides", []):
        target_number = int(target["slide_number"])
        target_family = str(target.get("family_hint", "content"))
        override = overrides.get(str(target_number))
        if override is not None:
            reference_index = int(override["reference_index"])
            reference_slide = _reference_page(references, reference_index, int(override["slide"]))
            match_mode = "override"
            warning = None
        else:
            candidates = []
            for reference_index, ledger in enumerate(references):
                for slide in ledger.get("slides", []):
                    if slide.get("family_hint") == target_family:
                        candidates.append((reference_index, ledger, slide, "same_family"))
            warning = None
            if not candidates:
                if target_family in STRICT_FAMILIES:
                    raise PlanError(f"no {target_family} reference page exists for target slide {target_number}")
                for reference_index, ledger in enumerate(references):
                    for slide in ledger.get("slides", []):
                        if slide.get("family_hint") == "content":
                            candidates.append((reference_index, ledger, slide, "content_fallback"))
                warning = f"target slide {target_number} used content fallback for {target_family}"
            if not candidates:
                raise PlanError(f"no credible reference page exists for target slide {target_number}")
            reference_index, reference_ledger, reference_slide, match_mode = min(
                candidates,
                key=lambda item: (
                    _score(target, item[2], int(source.get("slide_count", 1)), int(item[1].get("slide_count", 1))),
                    str(item[1].get("path", "")),
                    int(item[2].get("slide_number", 0)),
                ),
            )

        reference_ledger = references[reference_index]
        pages.append(
            {
                "target_slide": target_number,
                "target_family": target_family,
                "target_image": f"targets/page-{target_number:03d}.png",
                "reference_index": reference_index,
                "reference_deck": reference_ledger.get("path"),
                "reference_slide": int(reference_slide["slide_number"]),
                "reference_image": f"references/reference-{reference_index + 1:02d}/page-{int(reference_slide['slide_number']):03d}.png",
                "match_mode": match_mode,
                "warning": warning,
            }
        )
    return {
        "schema": "ppt_visual_plan.v1",
        "source": source.get("path"),
        "page_count": len(pages),
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Map target slides to reference-style slides.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--overrides")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    source = json.loads((run_dir / "source-ledger.json").read_text(encoding="utf-8"))
    references = json.loads((run_dir / "reference-ledger.json").read_text(encoding="utf-8"))
    overrides = json.loads(Path(args.overrides).read_text(encoding="utf-8")) if args.overrides else None
    plan = build_plan(source, references, overrides)
    (run_dir / "visual-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
