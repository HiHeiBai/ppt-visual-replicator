# Style1 Content Adaptation First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a high-quality, source-traceable Style1 rewrite of the frontMIND section by learning the content method of the three Style1 reference decks, without rebuilding the already-proven image and editable-PPT pipeline.

**Architecture:** Reuse the current PPT files, extracted text, and previews. First write a human-readable Style1 content method, then map the target frontMIND facts and assets, create a dynamic page plan, write the complete slide copy, and run a factual/style review. No new CLI, classifier, component library, or visual infrastructure is built in this phase.

**Inputs:**

- `新建文件夹/要改的PPT.pptx`, especially slides 3–12.
- Three PPTX files under `新建文件夹/风格1/`.
- `output/content-adapter-v1/extracted_slides.json`.
- `output/content-adapter-v1/01-style1-writing-style-guide.md`.
- `output/content-adapter-v1/04-full-slide-copy-v1.md` as a rejected draft to diagnose, not as approved content.

**Outputs:**

- `content-work/style1/reference-content-method.md`
- `content-work/style1/frontmind-source-map.md`
- `content-work/style1/frontmind-page-plan.md`
- `content-work/style1/frontmind-rewrite-v2.md`
- `content-work/style1/frontmind-review.md`

---

### Task 1: Extract the reusable Style1 content method

**Files:**
- Create: `content-work/style1/reference-content-method.md`

- [ ] **Step 1: Review the three reference decks at deck level**

For each reference deck, record:

- Main audience and report purpose.
- Chapter structure and research order.
- How many distinct narrative jobs occur: context, study introduction, design, baseline, efficacy, safety, interpretation, summary, discussion.
- Where the deck compresses multiple jobs into one page and where it separates them.
- Which pages contain editing notes or unfinished content and therefore cannot support a writing rule.

Every observation must cite the reference filename and slide number.

- [ ] **Step 2: Analyze complete research units instead of isolated pages**

Analyze at least these three complete research units:

- `2026 Post SC--1L DLBCL治疗进展.pptx`, slides 17–20: Pola-R-CHP real-world evidence unit.
- `2026 Post SC--FL&MZL&MCL治疗进展.pptx`, slides 4–6: CELESTIMO unit.
- `2026 Post SC--RR DLBCL治疗进展.pptx`, slides 9–15: STARGLO and biomarker follow-up unit.

For each unit, document the following fields:

```markdown
## Research unit

- Reference filename and exact slide range
- Opening method: how the clinical question is introduced
- Evidence sequence: how design, population, efficacy, safety, and limitations are ordered
- Title progression: what each title contributes to the argument
- Compression rule: which source details are retained, merged, or omitted
- Closing method: how the study is summarized without overstating evidence
```

Do not treat a deck page count or unit length as a target for the new deck.

- [ ] **Step 3: Extract title and paragraph writing patterns**

The method document must contain cited examples for:

- Generic title versus conclusion-led title.
- Data-led title.
- Study-introduction title.
- Safety title that balances risk and feasibility.
- Summary title that includes evidence boundaries.
- Paragraph structure for background, design, results, safety, and clinical meaning.

For each pattern, write when it applies and when it should not be used.

- [ ] **Step 4: Define Style1 content rules and anti-patterns**

The document must finish with these sections:

```markdown
## Stable Style1 content traits

## Rules that vary by study complexity

## Evidence-strength vocabulary

## What Style1 tends to retain

## What Style1 tends to merge or remove

## Anti-patterns found in the references

## Rewrite checklist
```

The rules must explicitly state that medical facts come only from the target deck; reference-deck facts are examples of writing, not source material.

- [ ] **Step 5: Validate the method document**

Run:

```bash
rg -n "Reference:|slides|Stable Style1 content traits|Evidence-strength vocabulary|Anti-patterns|Rewrite checklist" content-work/style1/reference-content-method.md
```

Expected: all required sections appear, and every claimed pattern has at least one filename-and-slide citation.

- [ ] **Step 6: Commit the Style1 method**

```bash
git add content-work/style1/reference-content-method.md
git commit -m "docs: define Style1 content adaptation method"
```

### Task 2: Build the frontMIND source-of-truth map

**Files:**
- Create: `content-work/style1/frontmind-source-map.md`

- [ ] **Step 1: Map target slides 3–12 before rewriting**

Create one section per source slide. The first heading must be `## Source slide 3: frontMIND study introduction`; subsequent headings use the real slide number and original title. Each section uses this structure:

```markdown
- Original role:
- Study fact statements:
- Exact numbers and units:
- Treatment names and abbreviations:
- Figures, tables, or screenshots to preserve:
- Citations and footnotes:
- Safety or evidence boundary:
- Relationship to adjacent slides:
```

All ten source slides, 3 through 12, must be represented even if later merged.

- [ ] **Step 2: Separate facts from interpretation**

After the ten slide sections, add:

```markdown
## Confirmed source facts

## Derived summaries allowed by the source

## Editorial bridges allowed for narrative flow

## Claims that the rewrite must not make
```

Examples of prohibited upgrades include turning an OS trend into a significant OS benefit or turning early safety observations into established long-term safety.

- [ ] **Step 3: Verify numeric coverage against the source PPT**

Run this read-only audit:

```bash
python3 - <<'PY'
import re
from pathlib import Path
from pptx import Presentation

prs = Presentation("新建文件夹/要改的PPT.pptx")
tokens = set()
for slide in list(prs.slides)[2:12]:
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False):
            tokens.update(re.findall(r"\b\d+(?:\.\d+)?%?|\b0\.\d+\b", shape.text))

mapped = Path("content-work/style1/frontmind-source-map.md").read_text(encoding="utf-8")
missing = sorted(token for token in tokens if token not in mapped)
print({"numeric_tokens": len(tokens), "missing": missing})
PY
```

Expected: `missing` is empty, or every intentionally omitted token is explained in the source map as duplicated, decorative, or non-content.

- [ ] **Step 4: Commit the source map**

```bash
git add content-work/style1/frontmind-source-map.md
git commit -m "docs: map frontMIND source evidence"
```

### Task 3: Create a dynamic Style1 page plan for frontMIND

**Files:**
- Create: `content-work/style1/frontmind-page-plan.md`

- [ ] **Step 1: Plan pages from content jobs, not a target count**

For every proposed page, use a descriptive heading such as `## Proposed page: frontMIND study question and mechanism`, followed by:

```markdown
- Working title direction:
- Reader takeaway:
- Source slides:
- Mandatory facts and numbers:
- Preserved figure/table/screenshot:
- Why this content is combined or separated:
- Style1 reference pattern used:
- Evidence boundary:
```

The plan may preserve, merge, split, or reorder source slides. The reason must be stated for every change.

- [ ] **Step 2: Add a source-coverage matrix**

```markdown
| Source slide | Proposed page(s) | Facts preserved | Asset preserved | Change reason |
|---:|---|---|---|---|
| 3 | Planned study-introduction page | Study identity and treatment question | Original paper screenshot | Establishes the study question before design and results |
```

The matrix must include slides 3–12 exactly once as source rows. A source slide may map to more than one proposed page.

- [ ] **Step 3: Check the plan against the Style1 method**

The bottom of the plan must answer:

- Does the sequence begin with a clinical or research question rather than a raw abstract title?
- Does every data page have a clear takeaway?
- Are efficacy, subgroup, OS maturity, and safety boundaries represented?
- Are repeated facts removed without losing evidence?
- Is the final study conclusion proportionate to the source evidence?

- [ ] **Step 4: Commit the page plan**

```bash
git add content-work/style1/frontmind-page-plan.md
git commit -m "docs: plan frontMIND Style1 content flow"
```

### Task 4: Write the complete frontMIND Style1 slide copy

**Files:**
- Create: `content-work/style1/frontmind-rewrite-v2.md`

- [ ] **Step 1: Write every planned page in final-copy form**

Use a descriptive heading such as `## Page: frontMIND study introduction`, followed by this structure for every page:

```markdown
### Title
Final title text.

### Lead message
One concise sentence when the page needs an interpretive lead; omit this section when the page is self-explanatory.

### Body
- Final bullet or paragraph text.
- Final bullet or paragraph text.

### Asset instruction
Exact source figure, table, or screenshot to preserve.

### Source trace
Target slides and fact-map sections supporting this page.
```

Do not leave alternative titles, drafting notes, bracketed choices, or unfinished copy.

- [ ] **Step 2: Apply evidence-strength language consistently**

- Use “显著改善” only when the source contains the supporting statistical result.
- Use “呈获益趋势” when the endpoint is directionally favorable without statistical confirmation.
- Use “显示”“提示”“支持进一步探索” for early or non-randomized evidence.
- Include OS maturity and safety boundaries where they affect interpretation.
- Preserve treatment names, abbreviations, sample sizes, time points, HR, CI, and P values exactly.

- [ ] **Step 3: Run a drafting-artifact scan**

Run:

```bash
rg -n "TODO|TBD|待确认|建议标题|可选|或者|换模板|加一个|\.\.\." content-work/style1/frontmind-rewrite-v2.md
```

Expected: no output.

- [ ] **Step 4: Commit the complete copy**

```bash
git add content-work/style1/frontmind-rewrite-v2.md
git commit -m "docs: rewrite frontMIND content in Style1"
```

### Task 5: Review the rewrite and decide whether to expand to the full deck

**Files:**
- Create: `content-work/style1/frontmind-review.md`

- [ ] **Step 1: Score five review dimensions**

Use a 1–5 score with written evidence for:

1. Source factual accuracy.
2. Information preservation.
3. Style1 content-method similarity.
4. Narrative clarity.
5. Evidence-boundary discipline.

Any score below 4 requires specific revisions to the source map, page plan, or slide copy before the sample passes.

- [ ] **Step 2: Perform line-by-line source tracing**

For every title, lead message, and numeric statement, record the supporting target slide. Mark each statement as:

- `source_fact`
- `derived_summary`
- `editorial_bridge`

No statement may remain unclassified.

- [ ] **Step 3: Record the go/no-go decision**

The review must end with exactly one decision:

- `GO — expand this method to the remaining Style1 studies`
- `NO-GO — revise the frontMIND sample before expanding`

If the result is NO-GO, list the failing review dimensions and exact sections to revise.

- [ ] **Step 4: Commit the review**

```bash
git add content-work/style1/frontmind-review.md
git commit -m "docs: review frontMIND Style1 rewrite"
```

## Completion criteria

This lean first phase is complete when:

- The Style1 method cites complete research units from all three reference decks.
- Target slides 3–12 have a complete fact and asset map.
- The proposed page count is explained by content, not predetermined.
- The rewrite contains final copy rather than suggestions or alternatives.
- Every major claim traces to the target deck.
- The review result is GO with all five dimensions scoring at least 4.
- No new image-generation, rendering, reconstruction, or generic analysis infrastructure has been built.
