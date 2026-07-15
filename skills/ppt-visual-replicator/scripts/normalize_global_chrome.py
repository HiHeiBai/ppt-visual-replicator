#!/usr/bin/env python3
"""Apply optional deck-wide title, footer, tag, and page-marker styling."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any


TAG_PATTERN = re.compile(r"^(Oral|Abstract)[\s-]?(70\d{2})$", re.IGNORECASE)
TAG_ID_PATTERN = re.compile(r"oral|tag|brand|label", re.IGNORECASE)
FOOTER_ID_PATTERN = re.compile(r"footer|document[_-]?code|confidential|internal[_-]?notice", re.IGNORECASE)
PAGE_ID_PATTERN = re.compile(r"page|counter", re.IGNORECASE)
LEGACY_MARKER_PATTERN = re.compile(
    r"atom[_-]?badge|footer[_-]?(molecule[_-]?)?badge|footer[_-]?brand(?:[_-]?mark)?|"
    r"footer[_-]?logo(?:[_-]?arc)?|page[_-]?(number|marker|ring|badge)|footer[_-]?page[_-]?(ring|badge)",
    re.IGNORECASE,
)


class ChromeError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChromeError(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ChromeError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _scaled(value: Any, scale: float) -> float:
    return round(float(value) * scale, 1)


def _normalized_tag(text: str) -> str | None:
    match = TAG_PATTERN.match(text.strip())
    if not match:
        return None
    kind = match.group(1).capitalize()
    return f"{kind}-{match.group(2)}"


def _source_tag(manifest: dict[str, Any]) -> str | None:
    for entry in manifest.get("text_inventory", []):
        if isinstance(entry, str):
            tag = _normalized_tag(entry)
            if tag:
                return tag
            continue
        if not isinstance(entry, dict) or not TAG_ID_PATTERN.search(str(entry.get("id", ""))):
            continue
        tag = _normalized_tag(str(entry.get("text", "")))
        if tag:
            return tag
    return None


def _page_number(page_dir: Path) -> int:
    match = re.fullmatch(r"page_(\d+)", page_dir.name)
    if not match:
        raise ChromeError(f"invalid page directory name: {page_dir.name}")
    return int(match.group(1))


def _in_page_range(slide_number: int, config: dict[str, Any]) -> bool:
    page_range = config.get("page_range")
    if page_range is not None:
        if not isinstance(page_range, list) or len(page_range) != 2:
            raise ChromeError("page_range must be [first_slide, last_slide]")
        if not int(page_range[0]) <= slide_number <= int(page_range[1]):
            return False
    return slide_number not in {int(value) for value in config.get("exclude_pages", [])}


def _remove_old_chrome(manifest: dict[str, Any], width: float, height: float) -> set[str]:
    removed_paths: set[str] = set()

    def keep_text(item: dict[str, Any]) -> bool:
        x, y, *_ = item.get("box_px", [0, 0])
        item_id = str(item.get("id", ""))
        text = str(item.get("text", "")).strip()
        top_tag = x > width * 0.7 and y < height * 0.16 and (
            TAG_ID_PATTERN.search(item_id) or _normalized_tag(text)
        )
        page_number = y > height * 0.84 and text.isdigit() and PAGE_ID_PATTERN.search(item_id)
        reserved = item_id in {"global-top-tag-text", "global-page-number"}
        return not (top_tag or page_number or reserved)

    def keep_shape(item: dict[str, Any]) -> bool:
        x, y, box_width, box_height = item.get("box_px", [0, 0, 0, 0])
        item_id = str(item.get("id", ""))
        top_tag = x > width * 0.7 and y < height * 0.16 and (
            TAG_ID_PATTERN.search(item_id)
            or (item.get("type") == "roundRect" and box_width < width * 0.18 and box_height < height * 0.12)
        )
        page_marker = y > height * 0.84 and PAGE_ID_PATTERN.search(item_id)
        reserved = item_id == "global-top-tag"
        return not (top_tag or page_marker or reserved)

    def keep_image(item: dict[str, Any]) -> bool:
        x, y, *_ = item.get("box_px", [0, 0])
        item_id = str(item.get("id", ""))
        legacy = x < width * 0.16 and y > height * 0.84 and LEGACY_MARKER_PATTERN.search(item_id)
        reserved = item_id == "global-page-marker"
        if legacy or reserved:
            if item.get("path"):
                removed_paths.add(str(item["path"]))
            return False
        return True

    manifest["text_boxes"] = [item for item in manifest.get("text_boxes", []) if keep_text(item)]
    manifest["shapes"] = [item for item in manifest.get("shapes", []) if keep_shape(item)]
    manifest["images"] = [item for item in manifest.get("images", []) if keep_image(item)]
    manifest["asset_provenance"] = [
        item for item in manifest.get("asset_provenance", []) if str(item.get("path", "")) not in removed_paths
    ]
    return removed_paths


def normalize_run(run_dir: str | Path, config_path: str | Path) -> dict[str, Any]:
    run = Path(run_dir).expanduser().resolve()
    config_file = Path(config_path).expanduser().resolve()
    config = _read_json(config_file)
    page_dirs = sorted(path for path in (run / "pages").glob("page_*"))
    if not page_dirs:
        raise ChromeError(f"no page directories found: {run / 'pages'}")

    font = str(config.get("font", "Microsoft YaHei"))
    title_config = config.get("title", {})
    footer_config = config.get("footer", {})
    tag_config = config.get("top_tag")
    marker_config = config.get("page_marker")
    marker_asset = None
    if marker_config:
        marker_asset = Path(str(marker_config.get("asset", ""))).expanduser().resolve()
        if not marker_asset.is_file():
            raise ChromeError(f"page marker asset does not exist: {marker_asset}")

    report: dict[str, Any] = {"pages": [], "warnings": []}
    for page_dir in page_dirs:
        slide_number = _page_number(page_dir)
        if not _in_page_range(slide_number, config):
            continue
        manifest_path = page_dir / "manifest.json"
        manifest = _read_json(manifest_path)
        source = manifest.get("source", {})
        width = float(source.get("width_px", 0))
        height = float(source.get("height_px", 0))
        if width <= 0 or height <= 0:
            raise ChromeError(f"manifest source dimensions are missing: {manifest_path}")
        # Chrome configuration is authored against a 1920x1080 source grid.
        # Scale horizontal and vertical measurements independently so 4:3 and
        # custom-aspect source pages do not drift vertically.
        scale_x = width / 1920.0
        scale_y = height / 1080.0
        scale_shape = min(scale_x, scale_y)
        _remove_old_chrome(manifest, width, height)

        per_page_title_sizes = {str(key): value for key, value in title_config.get("per_page_sizes", {}).items()}
        for item in manifest.get("text_boxes", []):
            _, y, *_ = item.get("box_px", [0, 0])
            item_id = str(item.get("id", ""))
            if title_config and y < height * 0.16 and "title" in item_id.lower():
                size = per_page_title_sizes.get(str(slide_number), title_config.get("size"))
                if size is not None:
                    item["font_size"] = _scaled(size, scale_y)
                item.update({"font": font, "font_size_source": "measured", "fit_text": False})
            if footer_config and y > height * 0.84 and FOOTER_ID_PATTERN.search(item_id):
                if footer_config.get("size") is not None:
                    item["font_size"] = _scaled(footer_config["size"], scale_y)
                item.update({"font": font, "font_size_source": "measured", "fit_text": False})

        if marker_config and marker_asset:
            size = _scaled(marker_config.get("size", 70), scale_shape)
            left = _scaled(marker_config.get("left", 32), scale_x)
            bottom = _scaled(marker_config.get("bottom", 28), scale_y)
            top = round(height - bottom - size, 1)
            assets_dir = page_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            asset_name = "global-page-marker.png"
            shutil.copy2(marker_asset, assets_dir / asset_name)
            asset_path = f"assets/{asset_name}"
            manifest.setdefault("images", []).append(
                {
                    "id": "global-page-marker",
                    "path": asset_path,
                    "box_px": [left, top, size, size],
                    "alt": "User-requested circular page-number marker",
                    "z_index": 180,
                }
            )
            manifest.setdefault("asset_provenance", []).append(
                {
                    "path": asset_path,
                    "source": asset_path,
                    "source_type": "user-provided",
                    "provenance_note": "Copied from the user-selected global page-number marker asset.",
                }
            )
            padding = _scaled(marker_config.get("text_vertical_padding", 5), scale_y)
            manifest.setdefault("text_boxes", []).append(
                {
                    "id": "global-page-number",
                    "text": str(slide_number),
                    "box_px": [left, top + padding, size, size - 2 * padding],
                    "font_size": _scaled(marker_config.get("font_size", 18), scale_y),
                    "font_size_source": "measured",
                    "fit_text": False,
                    "font": font,
                    "color": marker_config.get("color", "#FFFFFF"),
                    "bold": bool(marker_config.get("bold", True)),
                    "align": "ctr",
                    "valign": "ctr",
                    "z_index": 190,
                }
            )

        if tag_config:
            label_map = {str(key): str(value) for key, value in tag_config.get("labels", {}).items()}
            label = _normalized_tag(label_map.get(str(slide_number), "")) or _source_tag(manifest)
            if not label:
                report["warnings"].append(
                    {"slide": slide_number, "warning": "top tag skipped because the source has no explicit tag label"}
                )
            else:
                tag_width = _scaled(tag_config.get("width", 210), scale_x)
                tag_height = _scaled(tag_config.get("height", 44), scale_y)
                right = _scaled(tag_config.get("right", 60), scale_x)
                tag_left = round(width - right - tag_width, 1)
                tag_top = _scaled(tag_config.get("top", 42), scale_y)
                manifest.setdefault("shapes", []).append(
                    {
                        "id": "global-top-tag",
                        "type": "roundRect",
                        "box_px": [tag_left, tag_top, tag_width, tag_height],
                        "fill": tag_config.get("fill", "#0A479E"),
                        "stroke": "none",
                        "source_corner_radius_px": round(tag_height / 2, 1),
                        "corner_category": "pill",
                        "corner_reason": "User-requested global top-right tag.",
                        "z_index": 170,
                    }
                )
                inset_x = _scaled(tag_config.get("inset_x", 8), scale_x)
                inset_y = _scaled(tag_config.get("inset_y", 6), scale_y)
                manifest.setdefault("text_boxes", []).append(
                    {
                        "id": "global-top-tag-text",
                        "text": label,
                        "box_px": [
                            tag_left + inset_x,
                            tag_top + inset_y,
                            tag_width - 2 * inset_x,
                            tag_height - 2 * inset_y,
                        ],
                        "font_size": _scaled(tag_config.get("font_size", 15), scale_y),
                        "font_size_source": "measured",
                        "fit_text": False,
                        "font": font,
                        "color": tag_config.get("color", "#FFFFFF"),
                        "bold": bool(tag_config.get("bold", True)),
                        "align": "ctr",
                        "valign": "ctr",
                        "z_index": 180,
                    }
                )

        _write_json(manifest_path, manifest)
        report["pages"].append(slide_number)

    report["page_count"] = len(report["pages"])
    report_path = run / "chrome-normalization-report.json"
    _write_json(report_path, report)
    return {"report": str(report_path), **report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize optional global visual chrome in an editppt run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    print(json.dumps(normalize_run(args.run_dir, args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
