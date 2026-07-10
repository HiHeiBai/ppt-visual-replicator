# Reference Style Analysis Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested reference-PPT analysis pipeline that decomposes the Style1 and Style2 folders into slide catalogs, quality grades, content-pattern summaries, visual-system summaries, component signatures, rendered contact sheets, and reviewable reports.

**Architecture:** A small Python package discovers reference decks from TOML configuration, extracts native PPTX structure with `python-pptx`, assigns non-destructive role and quality suggestions, renders pages with the bundled LibreOffice/Poppler binaries, and writes deterministic JSON/Markdown artifacts under `reference-analysis/`. Automatic heuristics never promote a page to trusted A-grade; explicit review overrides own final role and grade decisions.

**Tech Stack:** Python 3.11+, `python-pptx` 1.0.2, Pillow 11, standard-library `tomllib`, pytest 8, LibreOffice headless, Poppler `pdftoppm`, uv.

---

## Scope boundary

This is the first independently testable implementation slice from the approved design. It implements reference-document decomposition only.

The following remain separate implementation plans after this slice is working:

1. Evidence Ledger, factual validation, and dynamic Page Planner.
2. Style1 and Style2 content adapters and frontMIND golden samples.
3. Image redesign, editable-PPT reconstruction, text reconciliation, and final QA.
4. Two installable Skill packages, migration of legacy files, and Obsidian bridge-card writeback.

## Execution prerequisite

Run implementation in a dedicated worktree. The source PPTX files are intentionally untracked, so copy only the input folder into the worktree:

```bash
cd "/Users/jy02929148qq.com/Documents/0709PPT复刻skill"
git worktree add .worktrees/reference-analysis-foundation -b codex/reference-analysis-foundation
rsync -a "新建文件夹/" ".worktrees/reference-analysis-foundation/新建文件夹/"
cd ".worktrees/reference-analysis-foundation"
```

Expected: the worktree is on `codex/reference-analysis-foundation`; `新建文件夹/风格1` contains three valid PPTX files and `新建文件夹/风格2` contains one valid PPTX file.

## Target file map

```text
.gitignore                                      Ignore runtime and local-only assets
pyproject.toml                                  Package metadata, dependencies, CLI entrypoint
configs/reference-sets.toml                     Style1/Style2 reference-folder mapping
configs/reference-review.toml                   Explicit page-grade and role overrides
docs/legacy-inventory.md                        Read-only map of existing experiments
src/ppt_style_lab/__init__.py                   Package version
src/ppt_style_lab/__main__.py                   python -m entrypoint
src/ppt_style_lab/cli.py                        CLI argument parsing
src/ppt_style_lab/reference_analysis/
  __init__.py                                   Public phase-one API
  discovery.py                                  Reference-set loading and PPTX discovery
  extract.py                                    Native PPTX structural extraction
  classify.py                                   Role candidates and quality suggestions
  render.py                                     PPTX rendering and contact-sheet generation
  summarize.py                                  Content, visual, and component aggregation
  reports.py                                    JSON and Markdown report writers
  pipeline.py                                   End-to-end orchestration
tests/reference_analysis/
  test_discovery.py                             Config and lock-file discovery tests
  test_extract.py                               Structural extraction tests
  test_classify.py                              Role/quality/override tests
  test_render.py                                Contact-sheet and binary-resolution tests
  test_summarize.py                             Dynamic profile aggregation tests
  test_pipeline.py                              End-to-end no-render integration test
reference-analysis/style1/                      Generated Style1 analysis artifacts
reference-analysis/style2/                      Generated Style2 analysis artifacts
```

### Task 1: Scaffold the package and preserve the legacy map

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `docs/legacy-inventory.md`
- Create: `src/ppt_style_lab/__init__.py`
- Create: `tests/reference_analysis/test_package.py`

- [ ] **Step 1: Write the failing package smoke test**

```python
# tests/reference_analysis/test_package.py
from ppt_style_lab import __version__


def test_package_has_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Add package metadata before installing dependencies**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "ppt-style-lab"
version = "0.1.0"
description = "Reference PPT style decomposition for dual medical deck skills"
requires-python = ">=3.11"
dependencies = [
  "python-pptx==1.0.2",
  "Pillow>=11,<12",
]

[project.scripts]
ppt-style-lab = "ppt_style_lab.cli:main"

[dependency-groups]
dev = ["pytest>=8.3,<9"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Install the isolated development environment and verify the test fails**

Run:

```bash
uv sync --group dev --no-install-project
PYTHONPATH=src .venv/bin/pytest tests/reference_analysis/test_package.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ppt_style_lab'`.

- [ ] **Step 4: Add the minimal package implementation**

```python
# src/ppt_style_lab/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 5: Record local-only assets and legacy experiments**

```gitignore
# .gitignore
.DS_Store
.venv/
.pytest_cache/
__pycache__/
*.py[cod]
.worktrees/
.~*.pptx
runs/
reference-analysis/**/rendered/
reference-analysis/**/decks/*/rendered/

# Original customer inputs and large experiment outputs remain on disk.
/新建文件夹/
/新建文件夹.zip
/output/
/dashiai-style1-prototype/
/style1-dashiai-ppt/
/style1-ppt-replicator/
```

```markdown
# Legacy experiment inventory

The following directories are preserved in the original workspace and are not source-of-truth implementation modules:

| Path | Status | Reusable evidence |
|---|---|---|
| `dashiai-style1-prototype/` | Legacy prototype | JSON-to-component rendering experiment |
| `style1-dashiai-ppt/` | Legacy prototype | Source-structure protection and editable export ideas |
| `style1-ppt-replicator/` | Legacy prototype | OOXML cloning, component slots, and validation ideas |
| `output/content-adapter-v1/` | Historical content experiment | Existing Style1 writing analysis, not approved content |
| `output/style2-writing-optimize/` | Rejected content route | Mechanical title/body replacement evidence |
| `output/style2-imagegen-full/` | Visual proof of concept | Full-page image quality benchmark |
| `output/image-redesign-to-ppt/` | Editable proof of concept | Object-level reconstruction benchmark |

No path in this table is deleted during the reference-analysis phase.
```

- [ ] **Step 6: Run the smoke test**

Run:

```bash
uv sync --group dev
uv run pytest tests/reference_analysis/test_package.py -q
```

Expected: `1 passed`.

- [ ] **Step 7: Commit the scaffold**

```bash
git add .gitignore pyproject.toml uv.lock docs/legacy-inventory.md src/ppt_style_lab/__init__.py tests/reference_analysis/test_package.py
git commit -m "chore: scaffold PPT style analysis package"
```

### Task 2: Discover configured reference decks without accepting lock files

**Files:**
- Create: `configs/reference-sets.toml`
- Create: `src/ppt_style_lab/reference_analysis/__init__.py`
- Create: `src/ppt_style_lab/reference_analysis/discovery.py`
- Create: `tests/reference_analysis/test_discovery.py`

- [ ] **Step 1: Write discovery tests**

```python
# tests/reference_analysis/test_discovery.py
from pathlib import Path

from ppt_style_lab.reference_analysis.discovery import load_reference_sets


def test_load_reference_sets_filters_office_lock_files(tmp_path: Path) -> None:
    style1 = tmp_path / "refs" / "style1"
    style2 = tmp_path / "refs" / "style2"
    style1.mkdir(parents=True)
    style2.mkdir(parents=True)
    (style1 / "a.pptx").touch()
    (style1 / ".~a.pptx").touch()
    (style1 / "notes.txt").touch()
    (style2 / "b.pptx").touch()
    config = tmp_path / "reference-sets.toml"
    config.write_text(
        '[style1]\nsource_dir = "refs/style1"\n'
        '[style2]\nsource_dir = "refs/style2"\n',
        encoding="utf-8",
    )

    result = load_reference_sets(tmp_path, config)

    assert [item.path.name for item in result["style1"].decks] == ["a.pptx"]
    assert [item.path.name for item in result["style2"].decks] == ["b.pptx"]


def test_load_reference_sets_rejects_missing_directory(tmp_path: Path) -> None:
    config = tmp_path / "reference-sets.toml"
    config.write_text('[style1]\nsource_dir = "missing"\n', encoding="utf-8")

    try:
        load_reference_sets(tmp_path, config)
    except FileNotFoundError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing reference directory must fail")
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/reference_analysis/test_discovery.py -q`

Expected: FAIL because `ppt_style_lab.reference_analysis.discovery` does not exist.

- [ ] **Step 3: Implement reference-set discovery**

```python
# src/ppt_style_lab/reference_analysis/discovery.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ReferenceDeck:
    style_id: str
    path: Path


@dataclass(frozen=True)
class ReferenceSet:
    style_id: str
    source_dir: Path
    decks: tuple[ReferenceDeck, ...]


def _valid_pptx(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".pptx" and not path.name.startswith(".~")


def load_reference_sets(project_root: Path, config_path: Path) -> dict[str, ReferenceSet]:
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    result: dict[str, ReferenceSet] = {}
    for style_id, config in sorted(data.items()):
        source_dir = (project_root / str(config["source_dir"])).resolve()
        if not source_dir.is_dir():
            raise FileNotFoundError(f"reference directory does not exist: {source_dir}")
        decks = tuple(
            ReferenceDeck(style_id=style_id, path=path)
            for path in sorted(source_dir.iterdir())
            if _valid_pptx(path)
        )
        if not decks:
            raise ValueError(f"reference directory has no valid PPTX files: {source_dir}")
        result[style_id] = ReferenceSet(style_id=style_id, source_dir=source_dir, decks=decks)
    return result
```

```python
# src/ppt_style_lab/reference_analysis/__init__.py
from .discovery import ReferenceDeck, ReferenceSet, load_reference_sets

__all__ = ["ReferenceDeck", "ReferenceSet", "load_reference_sets"]
```

```toml
# configs/reference-sets.toml
[style1]
source_dir = "新建文件夹/风格1"

[style2]
source_dir = "新建文件夹/风格2"
```

- [ ] **Step 4: Run discovery tests**

Run: `uv run pytest tests/reference_analysis/test_discovery.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Verify the real configuration**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
from ppt_style_lab.reference_analysis.discovery import load_reference_sets

sets = load_reference_sets(Path.cwd(), Path("configs/reference-sets.toml"))
print({key: len(value.decks) for key, value in sets.items()})
PY
```

Expected: `{'style1': 3, 'style2': 1}`.

- [ ] **Step 6: Commit discovery**

```bash
git add configs/reference-sets.toml src/ppt_style_lab/reference_analysis tests/reference_analysis/test_discovery.py
git commit -m "feat: discover configured reference decks"
```

### Task 3: Extract slide structure without forcing one title or role

**Files:**
- Create: `src/ppt_style_lab/reference_analysis/extract.py`
- Create: `tests/reference_analysis/test_extract.py`

- [ ] **Step 1: Write structural extraction tests**

```python
# tests/reference_analysis/test_extract.py
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from ppt_style_lab.reference_analysis.extract import extract_reference_deck


def build_fixture(path: Path) -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title = slide.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(9), Inches(0.7))
    run = title.text_frame.paragraphs[0].add_run()
    run.text = "结论型标题"
    run.font.size = Pt(28)
    title.fill.solid()
    title.fill.fore_color.rgb = RGBColor(0x00, 0x33, 0x99)
    body = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(5), Inches(2))
    body.text = "研究目的\n关键结果"
    table = slide.shapes.add_table(2, 3, Inches(7), Inches(1.5), Inches(5), Inches(2))
    table.table.cell(0, 0).text = "指标"
    prs.save(path)


def test_extract_reference_deck_preserves_structure_and_title_candidates(tmp_path: Path) -> None:
    pptx = tmp_path / "fixture.pptx"
    build_fixture(pptx)

    result = extract_reference_deck(pptx)

    assert result["schema"] == "reference_deck.v1"
    assert result["slide_count"] == 1
    assert result["master_count"] >= 1
    assert result["layout_count"] >= 1
    assert result["themes"]
    slide = result["slides"][0]
    assert slide["layout_name"]
    assert slide["shape_counts"]["table"] == 1
    assert slide["text_chars"] >= len("结论型标题研究目的关键结果指标")
    assert slide["title_candidates"][0]["text"] == "结论型标题"
    assert slide["title_candidates"][0]["score"] > 0
    assert slide["shapes"][0]["bbox"]["x"] >= 0
    assert slide["shapes"][0]["fill_color"] == "003399"
```

- [ ] **Step 2: Run the extraction test and verify it fails**

Run: `uv run pytest tests/reference_analysis/test_extract.py -q`

Expected: FAIL because `extract.py` does not exist.

- [ ] **Step 3: Implement recursive structural extraction**

```python
# src/ppt_style_lab/reference_analysis/extract.py
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree
import zipfile

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

EMU_PER_INCH = 914400


def clean_text(value: str) -> str:
    return "\n".join(" ".join(line.split()) for line in value.replace("\x0b", "\n").splitlines() if line.strip())


def _rgb(value: Any) -> str | None:
    try:
        rgb = value.rgb
    except Exception:
        return None
    return str(rgb).upper() if rgb else None


def _bbox(shape: Any) -> dict[str, float]:
    return {
        "x": round(int(shape.left) / EMU_PER_INCH, 4),
        "y": round(int(shape.top) / EMU_PER_INCH, 4),
        "width": round(int(shape.width) / EMU_PER_INCH, 4),
        "height": round(int(shape.height) / EMU_PER_INCH, 4),
    }


def _text_style(shape: Any) -> dict[str, list[Any]]:
    fonts: Counter[str] = Counter()
    sizes: Counter[float] = Counter()
    colors: Counter[str] = Counter()
    if getattr(shape, "has_text_frame", False):
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                if run.font.name:
                    fonts[run.font.name] += 1
                if run.font.size:
                    sizes[round(float(run.font.size.pt), 2)] += 1
                color = _rgb(run.font.color)
                if color:
                    colors[color] += 1
    return {
        "fonts": [[key, count] for key, count in fonts.most_common()],
        "sizes_pt": [[key, count] for key, count in sizes.most_common()],
        "colors": [[key, count] for key, count in colors.most_common()],
    }


def _shape_text(shape: Any) -> str:
    if getattr(shape, "has_table", False):
        values = [cell.text for row in shape.table.rows for cell in row.cells if cell.text.strip()]
        return clean_text("\n".join(values))
    if getattr(shape, "has_text_frame", False):
        return clean_text(shape.text)
    return ""


def _shape_kind(shape: Any) -> str:
    if getattr(shape, "has_table", False):
        return "table"
    if getattr(shape, "has_chart", False):
        return "chart"
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        return "picture"
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        return "group"
    if getattr(shape, "has_text_frame", False) and _shape_text(shape):
        return "text"
    return "shape"


def _package_metadata(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        media = [name for name in names if name.startswith("ppt/media/") and not name.endswith("/")]
        themes: list[str] = []
        for name in sorted(item for item in names if item.startswith("ppt/theme/") and item.endswith(".xml")):
            root = ElementTree.fromstring(package.read(name))
            themes.append(str(root.attrib.get("name") or Path(name).stem))
    return {"media_parts": len(media), "themes": themes}


def extract_shape(shape: Any) -> dict[str, Any]:
    text = _shape_text(shape)
    try:
        fill_color = _rgb(shape.fill.fore_color)
    except Exception:
        fill_color = None
    try:
        line_color = _rgb(shape.line.color)
    except Exception:
        line_color = None
    item: dict[str, Any] = {
        "name": str(shape.name),
        "kind": _shape_kind(shape),
        "bbox": _bbox(shape),
        "text": text,
        "text_chars": len(text),
        "text_style": _text_style(shape),
        "fill_color": fill_color,
        "line_color": line_color,
    }
    if getattr(shape, "has_table", False):
        item["table"] = {"rows": len(shape.table.rows), "cols": len(shape.table.columns)}
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        item["children"] = [extract_shape(child) for child in shape.shapes]
    return item


def flatten_shapes(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in items:
        flattened.append(item)
        flattened.extend(flatten_shapes(item.get("children", [])))
    return flattened


def title_candidates(shapes: list[dict[str, Any]], canvas_height: float) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, shape in enumerate(shapes):
        text = shape.get("text", "")
        if not text or len(text) > 220:
            continue
        bbox = shape["bbox"]
        sizes = [float(value) for value, _ in shape["text_style"]["sizes_pt"]]
        max_size = max(sizes, default=0.0)
        score = 0.0
        reasons: list[str] = []
        if bbox["y"] <= canvas_height * 0.22:
            score += 3.0
            reasons.append("top_zone")
        if max_size >= 24:
            score += 3.0
            reasons.append("large_font")
        if len(text) <= 80:
            score += 1.0
            reasons.append("concise")
        if "标题" in shape.get("name", "") or "Title" in shape.get("name", ""):
            score += 2.0
            reasons.append("title_placeholder")
        candidates.append({"shape_index": index, "text": text, "score": score, "reasons": reasons})
    return sorted(candidates, key=lambda item: (-item["score"], item["shape_index"]))


def extract_reference_deck(path: Path) -> dict[str, Any]:
    prs = Presentation(str(path))
    package = _package_metadata(path)
    width = round(int(prs.slide_width) / EMU_PER_INCH, 4)
    height = round(int(prs.slide_height) / EMU_PER_INCH, 4)
    slides: list[dict[str, Any]] = []
    for number, slide in enumerate(prs.slides, start=1):
        nested = [extract_shape(shape) for shape in slide.shapes]
        flat = flatten_shapes(nested)
        counts = Counter(item["kind"] for item in flat)
        slides.append(
            {
                "number": number,
                "layout_name": str(slide.slide_layout.name),
                "shapes": nested,
                "shape_counts": dict(sorted(counts.items())),
                "text_chars": sum(item["text_chars"] for item in flat),
                "title_candidates": title_candidates(flat, height),
            }
        )
    return {
        "schema": "reference_deck.v1",
        "file": path.name,
        "path": str(path),
        "slide_count": len(slides),
        "master_count": len(prs.slide_masters),
        "layout_count": sum(len(master.slide_layouts) for master in prs.slide_masters),
        "media_parts": package["media_parts"],
        "themes": package["themes"],
        "canvas": {"width_in": width, "height_in": height},
        "slides": slides,
    }
```

- [ ] **Step 4: Run extraction tests**

Run: `uv run pytest tests/reference_analysis/test_extract.py -q`

Expected: `1 passed`.

- [ ] **Step 5: Commit extraction**

```bash
git add src/ppt_style_lab/reference_analysis/extract.py tests/reference_analysis/test_extract.py
git commit -m "feat: extract reference slide structure"
```

### Task 4: Add role candidates, conservative quality grading, and manual overrides

**Files:**
- Create: `src/ppt_style_lab/reference_analysis/classify.py`
- Create: `configs/reference-review.toml`
- Create: `tests/reference_analysis/test_classify.py`

- [ ] **Step 1: Write classification and override tests**

```python
# tests/reference_analysis/test_classify.py
from pathlib import Path

from ppt_style_lab.reference_analysis.classify import (
    apply_review_overrides,
    annotate_deck,
    load_review_overrides,
)


def slide(number: int, text: str, counts: dict[str, int] | None = None) -> dict:
    return {
        "number": number,
        "shapes": [{"text": text, "children": []}],
        "shape_counts": counts or {"text": 1},
        "text_chars": len(text),
        "title_candidates": [],
    }


def test_heuristics_keep_valid_pages_at_b_until_review() -> None:
    deck = {"file": "demo.pptx", "slides": [slide(1, "完整封面"), slide(2, "目录")]}
    annotated = annotate_deck(deck)

    assert annotated["slides"][0]["quality"]["suggested_grade"] == "B"
    assert annotated["slides"][0]["quality"]["needs_review"] is True
    assert annotated["slides"][1]["role_candidates"][0]["role"] == "toc"


def test_draft_marker_is_c_grade() -> None:
    deck = {"file": "demo.pptx", "slides": [slide(3, "换模板 换美化形式")]}
    annotated = annotate_deck(deck)
    assert annotated["slides"][0]["quality"]["suggested_grade"] == "C"


def test_manual_override_owns_final_grade_and_role(tmp_path: Path) -> None:
    config = tmp_path / "review.toml"
    config.write_text(
        '[[overrides]]\nstyle = "style1"\ndeck = "demo.pptx"\nslide = 1\n'
        'grade = "A"\nrole = "cover"\nreason = "reviewed"\n',
        encoding="utf-8",
    )
    overrides = load_review_overrides(config)
    deck = annotate_deck({"file": "demo.pptx", "slides": [slide(1, "完整封面")]})
    result = apply_review_overrides("style1", deck, overrides)

    assert result["slides"][0]["quality"]["final_grade"] == "A"
    assert result["slides"][0]["final_role"] == "cover"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/reference_analysis/test_classify.py -q`

Expected: FAIL because `classify.py` does not exist.

- [ ] **Step 3: Implement candidate roles and conservative quality suggestions**

```python
# src/ppt_style_lab/reference_analysis/classify.py
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable
import tomllib

DRAFT_MARKERS = ("换模板", "加一个", "结果描述", "左右各放", "待补", "占位")


def _texts(shapes: Iterable[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for shape in shapes:
        if shape.get("text"):
            values.append(str(shape["text"]))
        values.extend(_texts(shape.get("children", [])))
    return values


def role_candidates(slide: dict[str, Any]) -> list[dict[str, Any]]:
    text = " ".join(_texts(slide.get("shapes", [])))
    compact = text.replace(" ", "")
    counts = slide.get("shape_counts", {})
    scores: dict[str, tuple[float, list[str]]] = {}

    def add(role: str, score: float, reason: str) -> None:
        previous_score, reasons = scores.get(role, (0.0, []))
        scores[role] = (previous_score + score, [*reasons, reason])

    if slide["number"] == 1:
        add("cover", 0.8, "first_slide")
    if "目录" in compact or "AGENDA" in text.upper():
        add("toc", 0.95, "agenda_keyword")
    if any(word in compact for word in ("研究设计", "研究方法", "入组标准", "治疗方案")):
        add("study_design", 0.8, "design_keyword")
    if any(word in compact for word in ("基线", "Baseline")) or counts.get("table", 0):
        add("table_or_baseline", 0.65, "table_or_baseline_signal")
    if any(word in compact for word in ("安全性", "不良事件", "AE", "CRS", "ICANS")):
        add("safety", 0.75, "safety_keyword")
    if any(word in compact for word in ("结论", "总结", "临床意义")):
        add("summary", 0.7, "summary_keyword")
    if counts.get("picture", 0) + counts.get("chart", 0) >= 2:
        add("figure_or_result", 0.6, "multiple_visuals")
    if not scores:
        add("content", 0.35, "fallback")
    return [
        {"role": role, "score": round(score, 3), "reasons": reasons}
        for role, (score, reasons) in sorted(scores.items(), key=lambda item: (-item[1][0], item[0]))
    ]


def quality_suggestion(slide: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(_texts(slide.get("shapes", [])))
    visual_count = sum(slide.get("shape_counts", {}).get(kind, 0) for kind in ("picture", "chart", "table"))
    reasons: list[str] = []
    grade = "B"
    if not text.strip() and visual_count == 0:
        grade = "C"
        reasons.append("blank_page")
    markers = [marker for marker in DRAFT_MARKERS if marker in text]
    if markers:
        grade = "C"
        reasons.append("draft_markers:" + ",".join(markers))
    if not reasons:
        reasons.append("requires_explicit_review_before_a_grade")
    return {"suggested_grade": grade, "final_grade": grade, "reasons": reasons, "needs_review": grade != "C"}


def annotate_deck(deck: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(deck)
    for slide in result["slides"]:
        slide["role_candidates"] = role_candidates(slide)
        slide["final_role"] = slide["role_candidates"][0]["role"]
        slide["quality"] = quality_suggestion(slide)
    return result


def load_review_overrides(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return list(tomllib.loads(path.read_text(encoding="utf-8")).get("overrides", []))


def apply_review_overrides(style_id: str, deck: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any]:
    result = deepcopy(deck)
    keyed = {
        (str(item["style"]), str(item["deck"]), int(item["slide"])): item
        for item in overrides
    }
    for slide in result["slides"]:
        override = keyed.get((style_id, result["file"], int(slide["number"])))
        if not override:
            continue
        slide["quality"]["final_grade"] = str(override["grade"])
        slide["quality"]["needs_review"] = False
        slide["quality"]["review_reason"] = str(override["reason"])
        if override.get("role"):
            slide["final_role"] = str(override["role"])
    return result
```

- [ ] **Step 4: Add explicit current-reference C-grade overrides**

```toml
# configs/reference-review.toml
[[overrides]]
style = "style1"
deck = "2026 Post SC--RR DLBCL治疗进展.pptx"
slide = 19
grade = "C"
reason = "contains editing instruction rather than finished slide content"

[[overrides]]
style = "style1"
deck = "2026 Post SC--RR DLBCL治疗进展.pptx"
slide = 23
grade = "C"
reason = "contains page-count editing note"

[[overrides]]
style = "style1"
deck = "2026 Post SC--RR DLBCL治疗进展.pptx"
slide = 30
grade = "C"
reason = "contains add-content editing note"

[[overrides]]
style = "style1"
deck = "2026 Post SC--RR DLBCL治疗进展.pptx"
slide = 35
grade = "C"
reason = "contains template replacement instruction"

[[overrides]]
style = "style1"
deck = "2026 Post SC--RR DLBCL治疗进展.pptx"
slide = 37
grade = "C"
reason = "contains template replacement instruction"
```

- [ ] **Step 5: Run classification tests**

Run: `uv run pytest tests/reference_analysis/test_classify.py -q`

Expected: `3 passed`.

- [ ] **Step 6: Commit classification and review configuration**

```bash
git add configs/reference-review.toml src/ppt_style_lab/reference_analysis/classify.py tests/reference_analysis/test_classify.py
git commit -m "feat: classify reference pages conservatively"
```

### Task 5: Render reference decks and build contact sheets

**Files:**
- Create: `src/ppt_style_lab/reference_analysis/render.py`
- Create: `tests/reference_analysis/test_render.py`

- [ ] **Step 1: Write renderer utility tests**

```python
# tests/reference_analysis/test_render.py
from pathlib import Path

from PIL import Image

from ppt_style_lab.reference_analysis.render import create_contact_sheet, resolve_binary


def test_resolve_binary_uses_explicit_executable(tmp_path: Path) -> None:
    binary = tmp_path / "tool"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    assert resolve_binary(binary, "tool") == binary


def test_create_contact_sheet_keeps_all_pages(tmp_path: Path) -> None:
    pages: list[Path] = []
    for number, color in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255)), start=1):
        path = tmp_path / f"slide-{number:03d}.png"
        Image.new("RGB", (320, 180), color).save(path)
        pages.append(path)
    output = tmp_path / "contact-sheet.png"

    create_contact_sheet(pages, output, columns=2)

    with Image.open(output) as image:
        assert image.width == 640
        assert image.height > 360
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/reference_analysis/test_render.py -q`

Expected: FAIL because `render.py` does not exist.

- [ ] **Step 3: Implement binary resolution, rendering, and montage creation**

```python
# src/ppt_style_lab/reference_analysis/render.py
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw


def resolve_binary(explicit: Path | None, name: str) -> Path:
    if explicit is not None:
        if explicit.is_file() and explicit.stat().st_mode & 0o111:
            return explicit
        raise FileNotFoundError(f"executable is unavailable: {explicit}")
    discovered = shutil.which(name)
    if not discovered:
        raise FileNotFoundError(f"executable is unavailable: {name}")
    return Path(discovered)


def render_reference_deck(
    pptx: Path,
    output_dir: Path,
    *,
    soffice: Path,
    pdftoppm: Path,
    dpi: int = 144,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ppt-style-render-") as raw_tmp:
        tmp = Path(raw_tmp)
        subprocess.run(
            [str(soffice), "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(pptx)],
            check=True,
            capture_output=True,
            text=True,
        )
        pdf = tmp / f"{pptx.stem}.pdf"
        if not pdf.exists():
            raise RuntimeError(f"LibreOffice did not create expected PDF: {pdf}")
        prefix = tmp / "page"
        subprocess.run(
            [str(pdftoppm), "-png", "-r", str(dpi), str(pdf), str(prefix)],
            check=True,
            capture_output=True,
            text=True,
        )
        def page_number(path: Path) -> int:
            match = re.search(r"(\d+)$", path.stem)
            if not match:
                raise RuntimeError(f"unexpected rendered page name: {path.name}")
            return int(match.group(1))

        sources = sorted(tmp.glob("page-*.png"), key=page_number)
        if not sources:
            raise RuntimeError(f"Poppler did not render pages for {pptx}")
        outputs: list[Path] = []
        for number, source in enumerate(sources, start=1):
            destination = output_dir / f"slide-{number:03d}.png"
            shutil.copy2(source, destination)
            outputs.append(destination)
        return outputs


def create_contact_sheet(pages: list[Path], output: Path, *, columns: int = 4, cell_width: int = 320) -> Path:
    if not pages:
        raise ValueError("contact sheet requires at least one page")
    with Image.open(pages[0]) as first:
        ratio = first.height / first.width
    cell_height = round(cell_width * ratio)
    label_height = 24
    rows = (len(pages) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * (cell_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, page in enumerate(pages):
        with Image.open(page) as image:
            thumb = image.convert("RGB").resize((cell_width, cell_height), Image.Resampling.LANCZOS)
        x = (index % columns) * cell_width
        y = (index // columns) * (cell_height + label_height)
        sheet.paste(thumb, (x, y))
        draw.text((x + 8, y + cell_height + 4), f"slide-{index + 1:03d}", fill="black")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output
```

- [ ] **Step 4: Run renderer tests**

Run: `uv run pytest tests/reference_analysis/test_render.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Commit renderer utilities**

```bash
git add src/ppt_style_lab/reference_analysis/render.py tests/reference_analysis/test_render.py
git commit -m "feat: render reference decks and contact sheets"
```

### Task 6: Aggregate content patterns, visual metrics, and component signatures

**Files:**
- Create: `src/ppt_style_lab/reference_analysis/summarize.py`
- Create: `tests/reference_analysis/test_summarize.py`

- [ ] **Step 1: Write dynamic aggregation tests**

```python
# tests/reference_analysis/test_summarize.py
from ppt_style_lab.reference_analysis.summarize import (
    build_component_library,
    build_content_patterns,
    build_visual_system,
)


def catalog() -> list[dict]:
    return [
        {
            "file": "a.pptx",
            "slides": [
                {
                    "number": 1,
                    "final_role": "cover",
                    "text_chars": 30,
                    "shape_counts": {"text": 2, "picture": 1},
                    "title_candidates": [{"text": "封面标题", "score": 7}],
                    "shapes": [
                        {
                            "text_style": {"fonts": [["Arial", 2]], "sizes_pt": [[28.0, 1]], "colors": [["003399", 1]]},
                            "fill_color": "EAF4FF",
                            "line_color": "20A7D8",
                            "bbox": {"x": 0.5, "y": 0.2, "width": 8.0, "height": 0.8},
                            "children": [],
                        }
                    ],
                },
                {
                    "number": 2,
                    "final_role": "table_or_baseline",
                    "text_chars": 200,
                    "shape_counts": {"text": 4, "table": 1},
                    "title_candidates": [{"text": "基线特征", "score": 6}],
                    "shapes": [],
                },
            ],
        }
    ]


def test_content_patterns_use_observed_density_and_roles() -> None:
    result = build_content_patterns(catalog())
    assert result["role_counts"] == {"cover": 1, "table_or_baseline": 1}
    assert result["role_transitions"] == {"cover->table_or_baseline": 1}
    assert result["title_patterns"]["descriptive"] >= 1
    assert result["text_density"]["min_chars"] == 30
    assert result["text_density"]["max_chars"] == 200


def test_visual_system_and_components_are_observed_not_hardcoded() -> None:
    visual = build_visual_system(catalog())
    components = build_component_library(catalog())
    assert visual["fonts"][0] == ["Arial", 2]
    assert visual["text_colors"][0] == ["003399", 1]
    assert visual["fill_colors"][0] == ["EAF4FF", 1]
    assert visual["line_colors"][0] == ["20A7D8", 1]
    assert visual["regions"][0] == ["top", 1]
    assert any(item["signature"] == "picture:1|text:2" for item in components["components"])
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run pytest tests/reference_analysis/test_summarize.py -q`

Expected: FAIL because `summarize.py` does not exist.

- [ ] **Step 3: Implement observed-data aggregators**

```python
# src/ppt_style_lab/reference_analysis/summarize.py
from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any, Iterable


def _slides(catalogs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [slide for deck in catalogs for slide in deck["slides"]]


def _shapes(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        result.append(item)
        result.extend(_shapes(item.get("children", [])))
    return result


def build_content_patterns(catalogs: list[dict[str, Any]]) -> dict[str, Any]:
    slides = _slides(catalogs)
    roles = Counter(slide["final_role"] for slide in slides)
    transitions: Counter[str] = Counter()
    for deck in catalogs:
        deck_roles = [slide["final_role"] for slide in deck["slides"]]
        transitions.update(f"{left}->{right}" for left, right in zip(deck_roles, deck_roles[1:]))
    densities = sorted(int(slide["text_chars"]) for slide in slides)
    titles = [
        slide["title_candidates"][0]["text"]
        for slide in slides
        if slide.get("title_candidates")
    ]
    title_patterns: Counter[str] = Counter()
    generic = {"目录", "研究背景", "研究设计", "基线特征", "研究结果", "安全性", "结论", "总结"}
    for title in titles:
        compact = "".join(title.split())
        if "?" in title or "？" in title:
            title_patterns["question"] += 1
        elif any(char.isdigit() for char in title) and any(token in title for token in ("%", "HR", "PFS", "OS", "ORR", "CR")):
            title_patterns["data_led"] += 1
        elif compact in generic:
            title_patterns["generic"] += 1
        else:
            title_patterns["descriptive"] += 1
    return {
        "schema": "content_patterns.v1",
        "slide_count": len(slides),
        "role_counts": dict(sorted(roles.items())),
        "role_transitions": dict(sorted(transitions.items())),
        "title_patterns": dict(sorted(title_patterns.items())),
        "text_density": {
            "min_chars": min(densities, default=0),
            "median_chars": int(median(densities)) if densities else 0,
            "max_chars": max(densities, default=0),
        },
        "observed_titles": titles,
    }


def build_visual_system(catalogs: list[dict[str, Any]]) -> dict[str, Any]:
    fonts: Counter[str] = Counter()
    sizes: Counter[float] = Counter()
    colors: Counter[str] = Counter()
    fills: Counter[str] = Counter()
    lines: Counter[str] = Counter()
    regions: Counter[str] = Counter()
    for slide in _slides(catalogs):
        for shape in _shapes(slide.get("shapes", [])):
            style = shape.get("text_style", {})
            fonts.update({str(key): int(count) for key, count in style.get("fonts", [])})
            sizes.update({float(key): int(count) for key, count in style.get("sizes_pt", [])})
            colors.update({str(key): int(count) for key, count in style.get("colors", [])})
            if shape.get("fill_color"):
                fills[str(shape["fill_color"])] += 1
            if shape.get("line_color"):
                lines[str(shape["line_color"])] += 1
            bbox = shape.get("bbox")
            if bbox:
                center_y = float(bbox["y"]) + float(bbox["height"]) / 2
                center_x = float(bbox["x"]) + float(bbox["width"]) / 2
                if center_y <= 1.2:
                    regions["top"] += 1
                elif center_y >= 6.6:
                    regions["footer"] += 1
                elif center_x <= 4.4:
                    regions["left"] += 1
                elif center_x >= 8.9:
                    regions["right"] += 1
                else:
                    regions["center"] += 1
    return {
        "schema": "visual_system.v1",
        "fonts": [[key, count] for key, count in fonts.most_common(20)],
        "font_sizes_pt": [[key, count] for key, count in sizes.most_common(20)],
        "text_colors": [[key, count] for key, count in colors.most_common(20)],
        "fill_colors": [[key, count] for key, count in fills.most_common(20)],
        "line_colors": [[key, count] for key, count in lines.most_common(20)],
        "regions": [[key, count] for key, count in regions.most_common()],
        "interpretation": "observed metrics only; reviewed stable features are added in a later profile review",
    }


def build_component_library(catalogs: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for deck in catalogs:
        for slide in deck["slides"]:
            signature = "|".join(
                f"{kind}:{count}" for kind, count in sorted(slide.get("shape_counts", {}).items()) if count
            )
            grouped.setdefault(signature, []).append(
                {"deck": deck["file"], "slide": slide["number"], "role": slide["final_role"]}
            )
    components = [
        {"signature": signature, "examples": examples, "frequency": len(examples)}
        for signature, examples in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    ]
    return {"schema": "component_library.v1", "components": components}
```

- [ ] **Step 4: Run aggregation tests**

Run: `uv run pytest tests/reference_analysis/test_summarize.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Commit aggregators**

```bash
git add src/ppt_style_lab/reference_analysis/summarize.py tests/reference_analysis/test_summarize.py
git commit -m "feat: summarize reference content and visuals"
```

### Task 7: Build the pipeline, reports, and CLI

**Files:**
- Create: `src/ppt_style_lab/reference_analysis/reports.py`
- Create: `src/ppt_style_lab/reference_analysis/pipeline.py`
- Create: `src/ppt_style_lab/cli.py`
- Create: `src/ppt_style_lab/__main__.py`
- Create: `tests/reference_analysis/test_pipeline.py`

- [ ] **Step 1: Write the no-render integration test**

```python
# tests/reference_analysis/test_pipeline.py
import json
from pathlib import Path

from pptx import Presentation

from ppt_style_lab.reference_analysis.pipeline import run_reference_analysis


def make_deck(path: Path, title: str) -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(0, 0, 4000000, 800000).text = title
    prs.save(path)


def test_pipeline_writes_independent_style_artifacts(tmp_path: Path) -> None:
    for style in ("style1", "style2"):
        folder = tmp_path / "refs" / style
        folder.mkdir(parents=True)
        make_deck(folder / f"{style}.pptx", f"{style} title")
    config = tmp_path / "reference-sets.toml"
    config.write_text(
        '[style1]\nsource_dir = "refs/style1"\n'
        '[style2]\nsource_dir = "refs/style2"\n',
        encoding="utf-8",
    )
    review = tmp_path / "review.toml"
    review.write_text("", encoding="utf-8")
    output = tmp_path / "analysis"

    summary = run_reference_analysis(tmp_path, config, review, output, render=False)

    assert summary["style1"] == {"decks": 1, "slides": 1}
    assert summary["style2"] == {"decks": 1, "slides": 1}
    assert json.loads((output / "style1" / "slide-catalog.json").read_text())["style"] == "style1"
    assert (output / "style2" / "reference-quality-report.md").exists()
    assert (output / "style1" / "anti-patterns.md").exists()
    assert (output / "style1" / "content-patterns.md").exists()
    assert (output / "style2" / "visual-system.md").exists()
```

- [ ] **Step 2: Run the integration test and verify it fails**

Run: `uv run pytest tests/reference_analysis/test_pipeline.py -q`

Expected: FAIL because `pipeline.py` does not exist.

- [ ] **Step 3: Implement deterministic report writers**

```python
# src/ppt_style_lab/reference_analysis/reports.py
from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_quality_report(path: Path, style_id: str, catalogs: list[dict[str, Any]]) -> Path:
    lines = [f"# {style_id} reference quality report", ""]
    for deck in catalogs:
        lines.extend([f"## {deck['file']}", "", "| Slide | Grade | Role | Reason |", "|---:|---|---|---|"])
        for slide in deck["slides"]:
            quality = slide["quality"]
            reason = quality.get("review_reason") or "; ".join(quality["reasons"])
            lines.append(f"| {slide['number']} | {quality['final_grade']} | {slide['final_role']} | {reason} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_anti_patterns(path: Path, style_id: str, catalogs: list[dict[str, Any]]) -> Path:
    lines = [f"# {style_id} anti-patterns", "", "Pages graded C are excluded as full-page references.", ""]
    for deck in catalogs:
        for slide in deck["slides"]:
            if slide["quality"]["final_grade"] == "C":
                reason = slide["quality"].get("review_reason") or "; ".join(slide["quality"]["reasons"])
                lines.append(f"- `{deck['file']}` slide {slide['number']}: {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_observed_profile(path: Path, title: str, value: dict[str, Any]) -> Path:
    body = json.dumps(value, ensure_ascii=False, indent=2)
    path.write_text(
        f"# {title}\n\nThis report contains observed metrics and requires review before becoming a stable style rule.\n\n```json\n{body}\n```\n",
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 4: Implement the end-to-end pipeline**

```python
# src/ppt_style_lab/reference_analysis/pipeline.py
from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from .classify import annotate_deck, apply_review_overrides, load_review_overrides
from .discovery import load_reference_sets
from .extract import extract_reference_deck
from .render import create_contact_sheet, render_reference_deck, resolve_binary
from .reports import write_anti_patterns, write_json, write_observed_profile, write_quality_report
from .summarize import build_component_library, build_content_patterns, build_visual_system


def deck_id(name: str) -> str:
    value = re.sub(r"[^\w.-]+", "-", Path(name).stem, flags=re.UNICODE).strip("-")
    return value or "deck"


def run_reference_analysis(
    project_root: Path,
    config_path: Path,
    review_path: Path,
    output_root: Path,
    *,
    render: bool,
    soffice_path: Path | None = None,
    pdftoppm_path: Path | None = None,
) -> dict[str, dict[str, int]]:
    reference_sets = load_reference_sets(project_root, config_path)
    overrides = load_review_overrides(review_path)
    summary: dict[str, dict[str, int]] = {}
    soffice = resolve_binary(soffice_path, "soffice") if render else None
    pdftoppm = resolve_binary(pdftoppm_path, "pdftoppm") if render else None

    for style_id, reference_set in reference_sets.items():
        style_out = output_root / style_id
        catalogs: list[dict[str, Any]] = []
        inventories: list[dict[str, Any]] = []
        pages_by_role: dict[str, list[Path]] = {}
        for reference in reference_set.decks:
            catalog = apply_review_overrides(style_id, annotate_deck(extract_reference_deck(reference.path)), overrides)
            for slide in catalog["slides"]:
                slide["style"] = style_id
                slide["deck"] = catalog["file"]
            catalogs.append(catalog)
            inventories.append(
                {
                    "file": catalog["file"],
                    "path": catalog["path"],
                    "slide_count": catalog["slide_count"],
                    "canvas": catalog["canvas"],
                    "master_count": catalog["master_count"],
                    "layout_count": catalog["layout_count"],
                    "media_parts": catalog["media_parts"],
                    "themes": catalog["themes"],
                }
            )
            deck_out = style_out / "decks" / deck_id(reference.path.name)
            write_json(deck_out / "slide-catalog.json", catalog)
            if render:
                pages = render_reference_deck(
                    reference.path,
                    deck_out / "rendered",
                    soffice=soffice,
                    pdftoppm=pdftoppm,
                )
                create_contact_sheet(pages, deck_out / "contact-sheet.png")
                for slide, page in zip(catalog["slides"], pages, strict=True):
                    pages_by_role.setdefault(slide["final_role"], []).append(page)

        all_slides = [slide for deck in catalogs for slide in deck["slides"]]
        write_json(style_out / "deck-inventory.json", {"schema": "deck_inventory.v1", "style": style_id, "decks": inventories})
        write_json(style_out / "slide-catalog.json", {"schema": "slide_catalog.v1", "style": style_id, "slides": all_slides})
        content_patterns = build_content_patterns(catalogs)
        visual_system = build_visual_system(catalogs)
        write_json(style_out / "content-patterns.json", content_patterns)
        write_json(style_out / "visual-system.json", visual_system)
        write_observed_profile(style_out / "content-patterns.md", f"{style_id} observed content patterns", content_patterns)
        write_observed_profile(style_out / "visual-system.md", f"{style_id} observed visual system", visual_system)
        write_json(style_out / "component-library.json", build_component_library(catalogs))
        write_quality_report(style_out / "reference-quality-report.md", style_id, catalogs)
        write_anti_patterns(style_out / "anti-patterns.md", style_id, catalogs)
        for role, pages in sorted(pages_by_role.items()):
            create_contact_sheet(pages, style_out / "page-type-contact-sheets" / f"{role}.png")
        summary[style_id] = {"decks": len(catalogs), "slides": len(all_slides)}
    return summary
```

- [ ] **Step 5: Implement the CLI entrypoints**

```python
# src/ppt_style_lab/cli.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .reference_analysis.pipeline import run_reference_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ppt-style-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze-references")
    analyze.add_argument("--project-root", type=Path, default=Path.cwd())
    analyze.add_argument("--config", type=Path, required=True)
    analyze.add_argument("--review-config", type=Path, required=True)
    analyze.add_argument("--out", type=Path, required=True)
    analyze.add_argument("--render", action="store_true")
    analyze.add_argument("--soffice", type=Path)
    analyze.add_argument("--pdftoppm", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "analyze-references":
        summary = run_reference_analysis(
            args.project_root.resolve(),
            args.config.resolve(),
            args.review_config.resolve(),
            args.out.resolve(),
            render=args.render,
            soffice_path=args.soffice,
            pdftoppm_path=args.pdftoppm,
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
```

```python
# src/ppt_style_lab/__main__.py
from .cli import main

main()
```

- [ ] **Step 6: Run the pipeline test**

Run: `uv run pytest tests/reference_analysis/test_pipeline.py -q`

Expected: `1 passed`.

- [ ] **Step 7: Run the complete unit suite**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 8: Commit pipeline and CLI**

```bash
git add src/ppt_style_lab/cli.py src/ppt_style_lab/__main__.py src/ppt_style_lab/reference_analysis/pipeline.py src/ppt_style_lab/reference_analysis/reports.py tests/reference_analysis/test_pipeline.py
git commit -m "feat: add reference analysis pipeline"
```

### Task 8: Run the analyzer on the real reference folders

**Files:**
- Generate: `reference-analysis/style1/deck-inventory.json`
- Generate: `reference-analysis/style1/slide-catalog.json`
- Generate: `reference-analysis/style1/content-patterns.json`
- Generate: `reference-analysis/style1/content-patterns.md`
- Generate: `reference-analysis/style1/visual-system.json`
- Generate: `reference-analysis/style1/visual-system.md`
- Generate: `reference-analysis/style1/component-library.json`
- Generate: `reference-analysis/style1/reference-quality-report.md`
- Generate: `reference-analysis/style1/anti-patterns.md`
- Generate: `reference-analysis/style1/decks/*/contact-sheet.png`
- Generate: `reference-analysis/style1/page-type-contact-sheets/*.png`
- Generate: equivalent files under `reference-analysis/style2/`

- [ ] **Step 1: Run all tests before the real analysis**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run reference analysis with the bundled renderers**

```bash
SOFFICE_BIN="/Users/jy02929148qq.com/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice"
PDFTOPPM_BIN="/Users/jy02929148qq.com/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm"

uv run ppt-style-lab analyze-references \
  --project-root . \
  --config configs/reference-sets.toml \
  --review-config configs/reference-review.toml \
  --out reference-analysis \
  --render \
  --soffice "$SOFFICE_BIN" \
  --pdftoppm "$PDFTOPPM_BIN"
```

Expected stdout:

```json
{"style1": {"decks": 3, "slides": 125}, "style2": {"decks": 1, "slides": 12}}
```

- [ ] **Step 3: Validate generated artifacts and lock-file exclusion**

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

root = Path("reference-analysis")
expected = {"style1": (3, 125), "style2": (1, 12)}
for style, (deck_count, slide_count) in expected.items():
    inventory = json.loads((root / style / "deck-inventory.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / style / "slide-catalog.json").read_text(encoding="utf-8"))
    assert len(inventory["decks"]) == deck_count
    assert len(catalog["slides"]) == slide_count
    assert all(not deck["file"].startswith(".~") for deck in inventory["decks"])
    assert (root / style / "reference-quality-report.md").stat().st_size > 0
    assert (root / style / "component-library.json").stat().st_size > 0
    assert (root / style / "content-patterns.md").stat().st_size > 0
    assert (root / style / "visual-system.md").stat().st_size > 0
    assert any((root / style / "page-type-contact-sheets").glob("*.png"))
print("reference-analysis validation: passed")
PY
```

Expected: `reference-analysis validation: passed`.

- [ ] **Step 4: Inspect the contact sheets and review report**

Open each generated `contact-sheet.png` and read both `reference-quality-report.md` files. Add an A-grade override only when a page is complete enough to be a trusted content or full-page visual exemplar. Keep uncertain pages at B; never infer A solely from heuristics.

For example, if Style2 slide 3 is accepted after visual and content inspection, append:

```toml
[[overrides]]
style = "style2"
deck = "63th ERA 2026 医学速递.pptx"
slide = 3
grade = "A"
role = "figure_or_result"
reason = "reviewed complete evidence page with reusable content and visual structure"
```

- [ ] **Step 5: Re-run after explicit review changes**

Run the Step 2 command again after editing `configs/reference-review.toml`.

Expected: the same deck and slide counts; reviewed pages show the chosen `final_grade` and `final_role` in `slide-catalog.json` and the quality report.

- [ ] **Step 6: Commit versioned analysis artifacts**

```bash
git add configs/reference-review.toml reference-analysis
git commit -m "data: add reviewed Style1 and Style2 reference analysis"
```

### Task 9: Verify phase-one completion and document the next-plan boundary

**Files:**
- Create: `docs/reference-analysis-usage.md`
- Modify: `docs/superpowers/specs/2026-07-10-dual-style-ppt-skills-design.md`

- [ ] **Step 1: Write the usage document**

````markdown
# Reference analysis usage

Run the analyzer with:

```bash
uv run ppt-style-lab analyze-references \
  --project-root . \
  --config configs/reference-sets.toml \
  --review-config configs/reference-review.toml \
  --out reference-analysis \
  --render \
  --soffice "$SOFFICE_BIN" \
  --pdftoppm "$PDFTOPPM_BIN"
```

Interpretation rules:

- A: reviewed full-page exemplar.
- B: usable partial structure or component; review before reuse.
- C: excluded full-page reference and recorded anti-pattern.
- `content-patterns.json` and `visual-system.json` contain observed data, not final creative judgments.
- Page count is never inferred as a fixed target from reference deck page counts.

The next implementation plan consumes these artifacts to build the Evidence Ledger and dynamic Page Planner.
````

- [ ] **Step 2: Mark the design phase status without claiming later phases are complete**

Change the design document status line to:

```markdown
- 状态：参考风格文档拆解基础设施已完成；事实底稿与内容规划待实施
```

- [ ] **Step 3: Run final verification**

Run:

```bash
uv run pytest -q
git diff --check
git status --short
```

Expected: all tests pass; `git diff --check` has no output; only the usage document and design status line are modified.

- [ ] **Step 4: Commit phase-one documentation**

```bash
git add docs/reference-analysis-usage.md docs/superpowers/specs/2026-07-10-dual-style-ppt-skills-design.md
git commit -m "docs: complete reference analysis foundation"
```

## Phase-one completion criteria

Phase one is complete only when all of the following are true:

- Style1 discovery reports three decks and 125 slides.
- Style2 discovery reports one deck and 12 slides.
- Office lock files are excluded.
- Every slide has structural data, multiple role candidates when applicable, a final role, a suggested grade, and a final grade.
- No page becomes A-grade without an explicit review override.
- Both styles have deck inventory, slide catalog, content patterns, visual metrics, component signatures, quality report, anti-pattern report, and contact sheets.
- Generated page counts are observations, never hardcoded output targets.
- All pytest tests pass from a clean uv environment.
- The legacy workspace remains intact and no original PPTX is overwritten.
