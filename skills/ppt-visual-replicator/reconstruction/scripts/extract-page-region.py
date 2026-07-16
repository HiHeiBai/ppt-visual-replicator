#!/usr/bin/env python3
"""Extract a self-contained visual region for editable reconstruction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def parse_box(value: str) -> tuple[int, int, int, int]:
    try:
        x, y, width, height = [int(round(float(part.strip()))) for part in value.split(",")]
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("box must be x,y,width,height") from exc
    if x < 0 or y < 0 or width < 1 or height < 1:
        raise argparse.ArgumentTypeError("box values must be non-negative and non-empty")
    return x, y, width, height


def extract_region(
    image_path: str | Path,
    box: tuple[int, int, int, int],
    output_path: str | Path,
) -> dict[str, object]:
    source = Path(image_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if not source.is_file() or not source.stat().st_size:
        raise ValueError(f"source image does not exist or is empty: {source}")
    x, y, width, height = box
    with Image.open(source) as image:
        source_width, source_height = image.size
        if x + width > source_width or y + height > source_height:
            raise ValueError(
                f"box {box} exceeds source bounds {source_width}x{source_height}"
            )
        if width >= source_width * 0.98 and height >= source_height * 0.98:
            raise ValueError("full-slide extraction is forbidden; select a self-contained region")
        region = image.crop((x, y, x + width, y + height))
        output.parent.mkdir(parents=True, exist_ok=True)
        region.save(output, format="PNG")
    return {
        "schema": "ppt_visual_source_region.v1",
        "source": str(source),
        "output": str(output),
        "box_px": [x, y, width, height],
        "source_size_px": [source_width, source_height],
        "source_type": "source-faithful-region",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract a screenshot, photo, or complex illustration region without image generation."
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--box", required=True, type=parse_box)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    report = extract_region(args.image, args.box, args.out)
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
