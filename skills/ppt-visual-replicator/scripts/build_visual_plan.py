#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STRICT_FAMILIES = {"cover", "table", "chart_figure"}


class PlanError(ValueError):
    pass


def _value(slide: dict[str, Any], key: str) -> int:
    return int(slide.get(key, 0) or 0)


def _signature_distance(left: dict[str, Any], right: dict[str, Any]) -> tuple[int, int]:
    object_difference = sum(
        abs(_value(left, key) - _value(right, key))
        for key in ("table_count", "picture_count", "chart_count")
    )
    text_difference = abs(_value(left, "text_chars") - _value(right, "text_chars"))
    return object_difference, text_difference


def _family_medoid(slides: list[dict[str, Any]]) -> dict[str, Any]:
    if not slides:
        raise PlanError("cannot select an anchor from an empty page family")

    def score(candidate: dict[str, Any]) -> tuple[int, int, int]:
        distances = [_signature_distance(candidate, other) for other in slides]
        return (
            sum(distance[0] for distance in distances),
            sum(distance[1] for distance in distances),
            _value(candidate, "slide_number"),
        )

    return min(slides, key=score)


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
    *,
    allow_fallback_decks: bool = False,
) -> dict[str, Any]:
    if not references:
        raise PlanError("at least one reference ledger is required")
    overrides = overrides or {}
    primary = references[0]
    target_families = sorted(
        {
            str(slide.get("family_hint", "content"))
            for slide in source.get("slides", [])
            if str(slide.get("slide_number")) not in overrides
        }
    )
    anchors: dict[str, dict[str, Any]] = {}
    for family in target_families:
        exact = [slide for slide in primary.get("slides", []) if slide.get("family_hint") == family]
        reference_index = 0
        match_mode = "family_anchor"
        warning = None
        if family == "ending" and not exact:
            exact = [slide for slide in primary.get("slides", []) if slide.get("family_hint") == "cover"]
            match_mode = "cover_fallback"
            warning = "primary reference deck has no ending page; used cover fallback"
        if not exact and family not in STRICT_FAMILIES:
            exact = [slide for slide in primary.get("slides", []) if slide.get("family_hint") == "content"]
            match_mode = "content_fallback"
            warning = f"primary reference deck used content fallback for {family}"
        if not exact and allow_fallback_decks:
            for candidate_index, ledger in enumerate(references[1:], start=1):
                candidate_pages = [
                    slide for slide in ledger.get("slides", []) if slide.get("family_hint") == family
                ]
                if candidate_pages:
                    reference_index = candidate_index
                    exact = candidate_pages
                    match_mode = "fallback_deck"
                    warning = f"used secondary reference deck for {family}"
                    break
        if not exact:
            raise PlanError(f"primary reference deck has no {family} page")
        anchor_slide = _family_medoid(exact)
        anchor_ledger = references[reference_index]
        anchors[family] = {
            "reference_index": reference_index,
            "reference_deck": anchor_ledger.get("path"),
            "reference_slide": int(anchor_slide["slide_number"]),
            "reference_image": f"references/reference-{reference_index + 1:02d}/page-{int(anchor_slide['slide_number']):03d}.png",
            "match_mode": match_mode,
            "warning": warning,
        }

    pages = []
    for target in source.get("slides", []):
        target_number = int(target["slide_number"])
        target_family = str(target.get("family_hint", "content"))
        override = overrides.get(str(target_number))
        if override is not None:
            reference_index = int(override["reference_index"])
            reference_slide = _reference_page(references, reference_index, int(override["slide"]))
            match_mode = "override"
            warning = (
                "explicit override uses a non-primary reference deck"
                if reference_index != 0
                else None
            )
        else:
            anchor = anchors[target_family]
            reference_index = int(anchor["reference_index"])
            reference_slide = _reference_page(
                references,
                reference_index,
                int(anchor["reference_slide"]),
            )
            match_mode = str(anchor["match_mode"])
            warning = anchor["warning"]

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
        "style_lock": {
            "primary_reference_index": 0,
            "primary_reference_deck": primary.get("path"),
            "allow_fallback_decks": allow_fallback_decks,
            "anchor_policy": "one_per_family",
            "family_anchors": anchors,
        },
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Map target slides to reference-style slides.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--overrides")
    parser.add_argument("--allow-fallback-decks", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    source = json.loads((run_dir / "source-ledger.json").read_text(encoding="utf-8"))
    references = json.loads((run_dir / "reference-ledger.json").read_text(encoding="utf-8"))
    overrides = json.loads(Path(args.overrides).read_text(encoding="utf-8")) if args.overrides else None
    plan = build_plan(
        source,
        references,
        overrides,
        allow_fallback_decks=args.allow_fallback_decks,
    )
    (run_dir / "visual-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
