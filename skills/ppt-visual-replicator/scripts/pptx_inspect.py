#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"p": P_NS, "a": A_NS, "r": R_NS, "rel": REL_NS}
CRITICAL_TOKEN_RE = re.compile(
    r"(?:HR|CI|OR|RR|P|SD|SE|N|BETA|ALPHA)\s*[=<>≤≥]?\s*[-+]?\d+(?:\.\d+)?%?|"
    r"\d+(?:\.\d+)?%|[-+]?\d+(?:\.\d+)?",
    re.IGNORECASE,
)


class InputError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slide_family(
    slide_number: int,
    slide_count: int,
    texts: list[str],
    picture_count: int,
    table_count: int,
    chart_count: int,
) -> str:
    joined = " ".join(texts).lower()
    compact = "".join(joined.split())
    if any(marker in joined for marker in ("thank you", "谢谢", "感谢聆听")):
        return "ending"
    if "目录" in compact or any(marker in joined for marker in ("agenda", "contents")):
        return "toc"
    if slide_number == 1:
        return "cover"
    if table_count:
        return "table"
    if chart_count or picture_count >= 2:
        return "chart_figure"
    if any(marker in joined for marker in ("结论", "总结", "conclusion", "summary")):
        return "conclusion"
    if picture_count == 1:
        return "image_content"
    if slide_number == slide_count and len(joined) <= 40:
        return "ending"
    if len(joined) <= 40 and picture_count == 0:
        return "section"
    return "content"


def _slide_paths(archive: ZipFile, presentation: ET.Element) -> list[str]:
    rels_root = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in rels_root.findall("rel:Relationship", NS)
        if item.attrib.get("Id") and item.attrib.get("Target")
    }
    paths: list[str] = []
    for slide_id in presentation.findall("p:sldIdLst/p:sldId", NS):
        rel_id = slide_id.attrib.get(f"{{{R_NS}}}id")
        if not rel_id or rel_id not in targets:
            raise InputError(f"presentation slide relationship is missing: {rel_id}")
        path = posixpath.normpath(posixpath.join("ppt", targets[rel_id]))
        if path not in archive.namelist():
            raise InputError(f"slide part is missing: {path}")
        paths.append(path)
    return paths


def inspect_pptx(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if source.name.startswith(".~"):
        raise InputError(f"Office lock files are not valid inputs: {source.name}")
    if source.suffix.lower() != ".pptx":
        raise InputError(f"expected a .pptx input: {source}")
    if not source.is_file():
        raise InputError(f"input does not exist: {source}")

    try:
        with ZipFile(source) as archive:
            required = {"ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"}
            missing = sorted(required.difference(archive.namelist()))
            if missing:
                raise InputError(f"PPTX is missing required parts: {', '.join(missing)}")
            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
            slide_paths = _slide_paths(archive, presentation)
            size = presentation.find("p:sldSz", NS)
            if size is None:
                raise InputError("PPTX has no slide size")
            width = int(size.attrib["cx"])
            height = int(size.attrib["cy"])
            slides = []
            for index, slide_path in enumerate(slide_paths, start=1):
                root = ET.fromstring(archive.read(slide_path))
                texts = [
                    " ".join((node.text or "").split())
                    for node in root.findall(".//a:t", NS)
                    if (node.text or "").strip()
                ]
                picture_count = len(root.findall(".//p:pic", NS))
                table_count = len(root.findall(".//a:tbl", NS))
                graphic_frames = root.findall(".//p:graphicFrame", NS)
                chart_count = sum(
                    1
                    for node in root.findall(".//a:graphicData", NS)
                    if "chart" in node.attrib.get("uri", "").lower()
                )
                joined = " ".join(texts)
                slides.append(
                    {
                        "slide_number": index,
                        "part": slide_path,
                        "texts": texts,
                        "text_chars": len(joined),
                        "picture_count": picture_count,
                        "table_count": table_count,
                        "chart_count": chart_count,
                        "graphic_frame_count": len(graphic_frames),
                        "critical_tokens": sorted(set(CRITICAL_TOKEN_RE.findall(joined))),
                        "family_hint": _slide_family(
                            index,
                            len(slide_paths),
                            texts,
                            picture_count,
                            table_count,
                            chart_count,
                        ),
                    }
                )
    except BadZipFile as exc:
        raise InputError(f"input is not a valid PPTX package: {source}") from exc
    except ET.ParseError as exc:
        raise InputError(f"input contains invalid OOXML: {source}") from exc

    return {
        "schema": "ppt_visual_source.v1",
        "path": str(source),
        "sha256": _sha256(source),
        "slide_count": len(slides),
        "slide_size": {
            "width_emu": width,
            "height_emu": height,
            "aspect_ratio": width / height,
        },
        "slides": slides,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a PPTX into a content-protection ledger.")
    parser.add_argument("pptx")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = inspect_pptx(args.pptx)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
