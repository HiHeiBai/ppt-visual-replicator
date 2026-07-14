# Optional Global Chrome Normalization

Use this only when the user explicitly asks to unify recurring deck elements after editable reconstruction. It is a post-pass over page manifests, not a generation route and not a calibration pipeline.

Create a small JSON config. All geometry and font sizes use a 1920×1080 baseline and are scaled to each page source width.

```json
{
  "page_range": [3, 46],
  "font": "Microsoft YaHei",
  "title": {
    "size": 31,
    "per_page_sizes": {"41": 21.5, "44": 21.5}
  },
  "footer": {"size": 11},
  "top_tag": {
    "fill": "#0A479E",
    "width": 210,
    "height": 44,
    "right": 60,
    "top": 42,
    "font_size": 15,
    "labels": {
      "41": "Abstract-7059",
      "44": "Abstract-7068"
    }
  },
  "page_marker": {
    "asset": "/absolute/path/to/page-marker.png",
    "size": 70,
    "left": 32,
    "bottom": 28,
    "font_size": 18
  }
}
```

Run:

```bash
python3 scripts/normalize_global_chrome.py \
  --run-dir "output/reconstruction" \
  --config "chrome.json"
```

The script removes earlier page-marker and top-tag objects only inside the explicitly selected page range, copies the selected marker asset into each page, keeps page numbers editable, and writes `chrome-normalization-report.json`.

Top-tag text is taken from an explicit `labels` entry or from an exact tag label in the original page `text_inventory`. It is never guessed from slide ranges or footer abstract numbers. If neither source exists, the tag is skipped and recorded as a warning.

After the post-pass, rebuild and validate every affected page, then run `editppt run finalize` again. A manifest edit without rebuilding and validating is not deliverable.
