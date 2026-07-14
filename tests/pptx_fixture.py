from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _slide_xml(texts, *, pictures=0, table=False, chart=False):
    text_nodes = "".join(
        f"<p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>"
        for text in texts
    )
    picture_nodes = "".join("<p:pic/>" for _ in range(pictures))
    table_node = (
        '<p:graphicFrame><a:graphic><a:graphicData uri="table"><a:tbl/></a:graphicData></a:graphic></p:graphicFrame>'
        if table
        else ""
    )
    chart_node = (
        '<p:graphicFrame><a:graphic><a:graphicData uri="chart"><a:chart/></a:graphicData></a:graphic></p:graphicFrame>'
        if chart
        else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}">
  <p:cSld><p:spTree>{text_nodes}{picture_nodes}{table_node}{chart_node}</p:spTree></p:cSld>
</p:sld>
"""


def write_fixture_pptx(path: Path, slides=None) -> Path:
    slides = slides or [
        {"texts": ["Quarterly Review 2026"]},
        {"texts": ["目录", "研究背景", "研究结果"]},
        {
            "texts": ["主要结果", "HR=0.75", "P=0.0194", "2年PFS 71.1%"],
            "pictures": 1,
            "table": True,
            "chart": True,
        },
        {"texts": ["THANK YOU"]},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    slide_ids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i}"/>' for i in range(1, len(slides) + 1)
    )
    presentation = f"""<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}">
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>
"""
    relationships = "".join(
        f'<Relationship Id="rId{i}" Type="slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, len(slides) + 1)
    )
    rels = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{REL_NS}">{relationships}</Relationships>
"""

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", rels)
        for index, spec in enumerate(slides, start=1):
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                _slide_xml(
                    spec.get("texts", []),
                    pictures=spec.get("pictures", 0),
                    table=spec.get("table", False),
                    chart=spec.get("chart", False),
                ),
            )
    return path

