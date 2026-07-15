#!/usr/bin/env python3
"""Prepare a complete PPTX deck for the direct per-page redraw workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx
from check_native_editability import assess_native_editability
from extract_title_styles import extract_title_styles
from prepare_direct_page import DirectRunError, is_generated_run_artifact, prepare_direct_page
from render_source_pages import SourceRenderError, _write_single_slide_pptx, render_pptx_to_pngs


class DirectDeckError(RuntimeError):
    pass


SPEED_PROFILES = ("fast", "balanced", "strict")
SOURCE_RENDERERS = ("auto", "quicklook", "libreoffice")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).expanduser().resolve().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _as_reference_images(
    value: str | Path | Sequence[str | Path] | None,
) -> list[str | Path]:
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        return [value]
    return list(value)


def _as_reference_slides(value: int | Sequence[int] | None) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    return [int(item) for item in value]


def _request_contract(
    ledger: dict[str, Any],
    *,
    target_slide: int | None,
    reference_image: str | Path | Sequence[str | Path] | None,
    reference_slide: int | Sequence[int] | None,
    reference_user_supplied: bool,
    style_brief: str | None,
    source_dpi: int,
    strict_text_protection: bool,
    speed_profile: str,
    full_page_imagegen: bool,
    style_contract: str | Path | None,
    source_renderer: str,
) -> dict[str, Any]:
    reference_images = _as_reference_images(reference_image)
    if reference_images and not reference_user_supplied:
        raise DirectDeckError(
            "reference images require --reference-user-supplied; generated or prior-run images "
            "must never become style references"
        )
    reference_slides = _as_reference_slides(reference_slide)
    if reference_slides and len(reference_slides) != len(reference_images):
        raise DirectDeckError(
            "reference slide metadata must be omitted or supplied once per reference image"
        )
    reference_inputs = []
    for index, image in enumerate(reference_images):
        path = Path(image).expanduser().resolve()
        if path.suffix.lower() != ".png" or not path.is_file() or not path.stat().st_size:
            raise DirectDeckError(f"reference image must be a readable PNG: {path}")
        if is_generated_run_artifact(path):
            raise DirectDeckError(
                f"refusing generated or preview output as a style reference: {path}; "
                "use a user-supplied reference image or a JSON style contract instead"
            )
        reference_inputs.append(
            {
                "path": str(path),
                "sha256": _sha256(path),
                "source_slide": reference_slides[index] if reference_slides else None,
                "origin": "user-supplied",
            }
        )
    contract = {
        "target_sha256": ledger["sha256"],
        "target_slide": target_slide,
        "source_dpi": int(source_dpi),
        "style_brief": style_brief.strip() if style_brief else None,
        "strict_text_protection": bool(strict_text_protection),
        "speed_profile": speed_profile,
        "source_renderer": source_renderer,
        "full_page_imagegen": bool(full_page_imagegen),
        "style_contract": None,
        "references": reference_inputs,
        "reference_user_supplied": bool(reference_user_supplied),
    }
    if style_contract is not None:
        path = Path(style_contract).expanduser().resolve()
        if not path.is_file():
            raise DirectDeckError(f"style contract must be a readable JSON file: {path}")
        try:
            style_value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DirectDeckError(f"style contract is not valid JSON: {path}") from exc
        if not isinstance(style_value, dict) or not style_value.get("name"):
            raise DirectDeckError("style contract must be a JSON object with a non-empty name")
        contract["style_contract"] = {"path": str(path), "sha256": _sha256(path), "name": style_value["name"]}
    contract["fingerprint"] = _stable_digest(contract)
    return contract


def _generation_route(
    slide: dict[str, Any], speed_profile: str, full_page_imagegen: bool
) -> tuple[str, str]:
    family = str(slide.get("family_hint") or "unknown")
    if full_page_imagegen:
        return "generate", "full-page imagegen is required for every unique page"
    if speed_profile == "strict":
        return "generate", "strict profile redraws every unique page"
    if speed_profile == "fast":
        if family == "cover":
            return "generate", "fast profile redraws the cover as the deck style seed"
        return "direct-rebuild", "fast profile preserves the page and skips whole-slide imagegen"
    if family in {"cover", "chart_figure"}:
        return "generate", f"balanced profile redraws {family} pages"
    return (
        "direct-rebuild",
        f"balanced profile preserves {family} content and applies shared deck chrome during reconstruction",
    )


def _build_generation_plan(
    destination: Path,
    ledger: dict[str, Any],
    page_runs: list[dict[str, Any]],
    *,
    speed_profile: str,
    style_fingerprint: str,
    full_page_imagegen: bool,
) -> dict[str, Any]:
    slide_by_number = {int(item["slide_number"]): item for item in ledger["slides"]}
    canonical_by_hash: dict[str, int] = {}
    counts = {"generate": 0, "direct-rebuild": 0, "reuse": 0}
    pages = []

    for page in page_runs:
        slide_number = int(page["target_slide"])
        source_sha256 = str(page["source_sha256"])
        slide = slide_by_number[slide_number]
        canonical_slide = canonical_by_hash.get(source_sha256)
        if canonical_slide is None:
            canonical_by_hash[source_sha256] = slide_number
            action, reason = _generation_route(slide, speed_profile, full_page_imagegen)
            reconstruction_action = "rebuild"
        else:
            action = "reuse"
            reason = f"source PNG is identical to slide {canonical_slide}"
            reconstruction_action = "reuse-canonical"

        prompt_path = destination / page["prompt"]
        cache_key = _stable_digest(
            {
                "source_sha256": source_sha256,
                "prompt_sha256": _sha256(prompt_path),
                "style_fingerprint": style_fingerprint,
                "speed_profile": speed_profile,
                "action": action,
            }
        )
        generation = {
            "action": action,
            "reason": reason,
            "canonical_slide": canonical_slide or slide_number,
            "cache_key": cache_key,
            "status": "ready" if action == "direct-rebuild" else "pending",
        }
        reconstruction = {
            "action": reconstruction_action,
            "profile": speed_profile,
            "canonical_slide": canonical_slide or slide_number,
        }
        page.update(
            {
                "family_hint": slide.get("family_hint"),
                "generation": generation,
                "reconstruction": reconstruction,
            }
        )
        page_run_path = destination / page["run_dir"] / "run.json"
        page_run = json.loads(page_run_path.read_text(encoding="utf-8"))
        page_run["speed_profile"] = speed_profile
        page_run["generation"] = generation
        page_run["reconstruction"] = reconstruction
        _write_json(page_run_path, page_run)
        counts[action] += 1
        pages.append(
            {
                "target_slide": slide_number,
                "family_hint": slide.get("family_hint"),
                "source_sha256": source_sha256,
                "generation": generation,
                "reconstruction": reconstruction,
            }
        )

    return {
        "schema": "ppt_visual_generation_plan.v1",
        "speed_profile": speed_profile,
        "summary": {
            **counts,
            "total_pages": len(page_runs),
            "whole_slide_imagegen_calls": counts["generate"],
            "whole_slide_imagegen_calls_avoided": counts["direct-rebuild"] + counts["reuse"],
        },
        "shared_assets": {
            "directory": "shared-assets",
            "index": "shared-assets/index.json",
            "policy": "reuse-before-generate",
        },
        "pages": pages,
    }


def _refresh_resume_status(destination: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    by_slide = {int(page["target_slide"]): page for page in manifest.get("pages", [])}
    complete = True
    for page in manifest.get("pages", []):
        generation = page.get("generation") or {}
        action = generation.get("action")
        if action == "generate":
            ready = (destination / page["generated_image"]).is_file()
        elif action == "direct-rebuild":
            ready = True
        elif action == "reuse":
            canonical = by_slide.get(int(generation.get("canonical_slide") or 0), {})
            canonical_action = (canonical.get("generation") or {}).get("action")
            ready = canonical_action == "direct-rebuild" or bool(
                canonical and (destination / canonical["generated_image"]).is_file()
            )
        else:
            ready = False
        generation["status"] = "ready" if ready else "pending"
        page["generation"] = generation
        complete = complete and ready
        page_run_path = destination / page["run_dir"] / "run.json"
        if page_run_path.is_file():
            page_run = json.loads(page_run_path.read_text(encoding="utf-8"))
            page_run["generation"] = generation
            _write_json(page_run_path, page_run)
    manifest["status"] = "generation-ready" if complete else "prepared"
    manifest["resume"] = {
        "reused_existing_run": True,
        "generation_ready": complete,
    }
    _write_json(destination / "deck-run.json", manifest)
    plan_path = destination / str(manifest.get("generation_plan") or "generation-plan.json")
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan_pages = {int(page["target_slide"]): page for page in plan.get("pages", [])}
        for page in manifest.get("pages", []):
            planned = plan_pages.get(int(page["target_slide"]))
            if planned:
                planned["generation"] = page["generation"]
        _write_json(plan_path, plan)
    return manifest


def prepare_direct_deck(
    target: str | Path,
    run_dir: str | Path,
    *,
    target_slide: int | None = None,
    reference_image: str | Path | Sequence[str | Path] | None = None,
    reference_slide: int | Sequence[int] | None = None,
    reference_user_supplied: bool = False,
    style_brief: str | None = None,
    source_dpi: int = 192,
    strict_text_protection: bool = False,
    speed_profile: str = "balanced",
    full_page_imagegen: bool = False,
    style_contract: str | Path | None = None,
    source_renderer: str = "auto",
    force_reconstruct: bool = False,
    resume: bool = False,
    renderer: Callable[..., dict[str, Any]] = render_pptx_to_pngs,
) -> dict[str, Any]:
    destination = Path(run_dir).expanduser().resolve()
    if speed_profile not in SPEED_PROFILES:
        raise DirectDeckError(
            f"speed profile must be one of {', '.join(SPEED_PROFILES)}: {speed_profile}"
        )
    if source_renderer not in SOURCE_RENDERERS:
        raise DirectDeckError(
            "source renderer must be one of "
            f"{', '.join(SOURCE_RENDERERS)}: {source_renderer}"
        )
    try:
        ledger = inspect_pptx(target)
    except InputError as exc:
        raise DirectDeckError(str(exc)) from exc

    # A fully native deck is already the correct editable deliverable.  Do
    # not pass it through image generation merely because this command was
    # invoked: imagegen redraw is visually lossy and cannot improve the source
    # when no restyle was requested.  A caller may opt in to reconstruction
    # only with an explicit force flag.
    try:
        native_check = assess_native_editability(target, target_slide)
    except InputError as exc:
        raise DirectDeckError(str(exc)) from exc
    has_restyle_request = bool(reference_image or style_brief or style_contract)
    title_styles = extract_title_styles(target, target_slide)
    preserve_native = bool(
        native_check["preserve_recommended"]
        and not force_reconstruct
        and not has_restyle_request
    )
    if target_slide is not None:
        available = {int(slide["slide_number"]) for slide in ledger["slides"]}
        if target_slide not in available:
            raise DirectDeckError(f"target slide does not exist: {target_slide}")
    request_contract = _request_contract(
        ledger,
        target_slide=target_slide,
        reference_image=reference_image,
        reference_slide=reference_slide,
        reference_user_supplied=reference_user_supplied,
        style_brief=style_brief,
        source_dpi=source_dpi,
        strict_text_protection=strict_text_protection,
        speed_profile=speed_profile,
        full_page_imagegen=full_page_imagegen,
        style_contract=style_contract,
        source_renderer=source_renderer,
    )
    if destination.exists():
        if not resume:
            raise DirectDeckError(f"run directory already exists: {destination}")
        deck_run = destination / "deck-run.json"
        if not deck_run.is_file():
            raise DirectDeckError(f"existing run has no deck-run.json: {destination}")
        manifest = json.loads(deck_run.read_text(encoding="utf-8"))
        existing_fingerprint = (manifest.get("request_contract") or {}).get("fingerprint")
        if existing_fingerprint != request_contract["fingerprint"]:
            raise DirectDeckError(
                "existing run does not match the target, references, style contract/brief, DPI, text mode, or speed profile"
            )
        return _refresh_resume_status(destination, manifest)

    destination.mkdir(parents=True)
    if preserve_native:
        final = destination / "reconstruction" / "final" / "origin_edited.pptx"
        final.parent.mkdir(parents=True)
        if target_slide is None:
            shutil.copy2(Path(ledger["path"]), final)
        else:
            _write_single_slide_pptx(Path(ledger["path"]), final, target_slide)
        _write_json(destination / "native-editability.json", native_check)
        _write_json(destination / "title-styles.json", title_styles)
        manifest = {
            "schema": "ppt_visual_direct_deck.v3",
            "status": "native-source-preserved",
            "target_pptx": ledger["path"],
            "target_sha256": ledger["sha256"],
            "slide_count": int(native_check["selected_slide_count"]),
            "target_slide_numbers": list(native_check["selected_slide_numbers"]),
            "native_editability": "native-editability.json",
            "title_styles": "title-styles.json",
            "native_source_preserved": {
                "output": "reconstruction/final/origin_edited.pptx",
                "sha256": _sha256(final),
                "reason": native_check["reason"],
            },
            "next_action": "Open the preserved output in macOS Quick Look and deliver it; do not start image generation or reconstruction.",
        }
        _write_json(destination / "deck-run.json", manifest)
        return manifest
    try:
        _write_json(destination / "native-editability.json", native_check)
        _write_json(destination / "title-styles.json", title_styles)
        # Quick Look is more faithful for an individual slide, but it creates
        # a complete temporary PPTX and launches once per page. For a fast
        # deck run, use the already-supported one-pass LibreOffice/PDF route
        # unless the caller explicitly requested another renderer.
        effective_renderer = source_renderer
        if source_renderer == "auto" and speed_profile == "fast" and ledger["slide_count"] > 1:
            effective_renderer = "libreoffice"
        try:
            render_report = renderer(
                ledger["path"],
                destination / "source-pages",
                dpi=source_dpi,
                ledger=ledger,
                first_slide=target_slide,
                last_slide=target_slide,
                renderer=effective_renderer,
            )
        except SourceRenderError:
            # A fast run must not become unavailable because the batch route
            # is missing or rejects a particular deck. Auto mode can retain
            # compatibility by falling back to the previous Quick Look path.
            if source_renderer != "auto" or effective_renderer != "libreoffice":
                raise
            render_report = renderer(
                ledger["path"],
                destination / "source-pages",
                dpi=source_dpi,
                ledger=ledger,
                first_slide=target_slide,
                last_slide=target_slide,
                renderer="quicklook",
            )
            render_report["fallback_from"] = "libreoffice"
        selected_slides = [
            slide
            for slide in ledger["slides"]
            if target_slide is None or int(slide["slide_number"]) == target_slide
        ]
        run_ledger = {**ledger, "slide_count": len(selected_slides), "slides": selected_slides}
        _write_json(destination / "source-ledger.json", run_ledger)
        if style_contract is not None:
            shutil.copy2(Path(style_contract).expanduser().resolve(), destination / "style-contract.json")
        (destination / "shared-assets").mkdir(parents=True)
        _write_json(
            destination / "shared-assets" / "index.json",
            {
                "schema": "ppt_visual_shared_assets.v1",
                "speed_profile": speed_profile,
                "assets": [],
            },
        )

        page_runs: list[dict[str, Any]] = []
        for page in render_report["pages"]:
            slide_number = int(page["slide_number"])
            page_dir = destination / "pages" / f"slide-{slide_number:03d}"
            page_manifest = prepare_direct_page(
                ledger["path"],
                target_slide=slide_number,
                source_image=page["path"],
                reference_image=reference_image,
                reference_slide=reference_slide,
                reference_user_supplied=reference_user_supplied,
                style_brief=style_brief,
                style_contract=style_contract,
                strict_text_protection=strict_text_protection,
                run_dir=page_dir,
                ledger=ledger,
            )
            page_manifest["inputs"]["source"].update(
                {
                    "mode": "auto-rendered-pptx",
                    "path": ledger["path"],
                    "source_pptx_sha256": ledger["sha256"],
                    "target_slide": slide_number,
                }
            )
            page_manifest["source_render_report"] = "../../source-pages/render-report.json"
            _write_json(page_dir / "run.json", page_manifest)
            page_runs.append(
                {
                    "target_slide": slide_number,
                    "run_dir": str(page_dir.relative_to(destination)),
                    "source_image": str((page_dir / "source-content.png").relative_to(destination)),
                    "prompt": str((page_dir / "direct-image-prompt.txt").relative_to(destination)),
                    "generated_image": str((page_dir / "generated.png").relative_to(destination)),
                    "reconstruction_dir": str((page_dir / "reconstruction").relative_to(destination)),
                    "source_sha256": page_manifest["inputs"]["source"]["sha256"],
                }
            )
    except (DirectRunError, SourceRenderError, OSError, ValueError, KeyError) as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise DirectDeckError(str(exc)) from exc
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    style_mode = "default"
    if page_runs:
        first_run = json.loads(
            (destination / page_runs[0]["run_dir"] / "run.json").read_text(encoding="utf-8")
        )
        style_mode = first_run["style_mode"]
    generation_plan = _build_generation_plan(
        destination,
        ledger,
        page_runs,
        speed_profile=speed_profile,
        style_fingerprint=request_contract["fingerprint"],
        full_page_imagegen=full_page_imagegen,
    )
    _write_json(destination / "generation-plan.json", generation_plan)
    manifest = {
        "schema": "ppt_visual_direct_deck.v2",
        "status": "prepared",
        "target_pptx": ledger["path"],
        "target_sha256": ledger["sha256"],
        "slide_count": len(page_runs),
        "target_slide_numbers": [int(page["target_slide"]) for page in page_runs],
        "style_mode": style_mode,
        "speed_profile": speed_profile,
        "source_renderer": source_renderer,
        "text_protection_mode": "strict-native" if strict_text_protection else "visual-ocr",
        "style_brief": style_brief.strip() if style_brief else None,
        "style_contract": "style-contract.json" if style_contract is not None else None,
        "request_contract": request_contract,
        "source_ledger": "source-ledger.json",
        "source_render_dir": "source-pages",
        "source_render_report": "source-pages/render-report.json",
        "title_styles": "title-styles.json",
        "generation_plan": "generation-plan.json",
        "shared_assets": "shared-assets/index.json",
        "generation_summary": generation_plan["summary"],
        "pages": page_runs,
        "next_action": "Follow generation-plan.json, reuse shared assets, stage reconstruction inputs, then reconstruct in slide order.",
    }
    _write_json(destination / "deck-run.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a target PPTX and prepare a selected slide or complete deck for direct image generation."
    )
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--target-slide",
        type=int,
        help="Prepare one selected source slide as a one-page direct run. Omit for the complete deck.",
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--reference-image", action="append")
    parser.add_argument("--reference-slide", action="append", type=int)
    parser.add_argument(
        "--reference-user-supplied",
        action="store_true",
        help="Required when passing a reference image; never use this for a generated or prior-run page.",
    )
    parser.add_argument("--style-brief")
    parser.add_argument(
        "--style-contract",
        help="Optional JSON file that locks deck-level colors, typography, and reference-content rules.",
    )
    parser.add_argument("--source-dpi", type=int, default=192)
    parser.add_argument(
        "--source-renderer",
        choices=SOURCE_RENDERERS,
        default="auto",
        help="Source page renderer. In a multi-page fast run, auto uses one batch LibreOffice render and falls back to Quick Look.",
    )
    parser.add_argument("--strict-text-protection", action="store_true")
    parser.add_argument(
        "--speed-profile",
        choices=SPEED_PROFILES,
        default="balanced",
        help="fast minimizes redraws, balanced redraws visual pages, strict redraws every unique page.",
    )
    parser.add_argument(
        "--full-page-imagegen",
        action="store_true",
        help="Redraw every unique slide as one complete imagegen page.",
    )
    parser.add_argument(
        "--force-reconstruct",
        action="store_true",
        help="Bypass native-source preservation only when a reconstruction is explicitly required.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse a matching existing run directory and completed generated.png files.",
    )
    args = parser.parse_args()
    manifest = prepare_direct_deck(
        args.target,
        args.run_dir,
        target_slide=args.target_slide,
        reference_image=args.reference_image,
        reference_slide=args.reference_slide,
        reference_user_supplied=args.reference_user_supplied,
        style_brief=args.style_brief,
        source_dpi=args.source_dpi,
        strict_text_protection=args.strict_text_protection,
        speed_profile=args.speed_profile,
        full_page_imagegen=args.full_page_imagegen,
        style_contract=args.style_contract,
        source_renderer=args.source_renderer,
        force_reconstruct=args.force_reconstruct,
        resume=args.resume,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
