# PPT Visual Replicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable `ppt-visual-replicator` Skill that plans reference-style image edits and validates the editable PPT reconstructed by `editppt` without mixing in content rewriting.

**Architecture:** Keep the Skill as a thin orchestration layer around read-only OOXML inspection, deterministic page matching, serial `editppt image edit` jobs, and the existing `image-to-editable-ppt` reconstruction contract. Use Python standard-library code for manifests and validation so the Skill can be tested without creating or editing presentation files programmatically.

**Tech Stack:** Python 3 standard library, OOXML/ZIP, `unittest`, LibreOffice/Poppler command discovery, installed `editppt` CLI.

---

### Task 1: Initialize and validate the Skill package

**Files:**
- Create: `skills/ppt-visual-replicator/SKILL.md`
- Create: `skills/ppt-visual-replicator/agents/openai.yaml`
- Create: `skills/ppt-visual-replicator/references/content-protection.md`
- Create: `skills/ppt-visual-replicator/references/page-matching.md`
- Create: `skills/ppt-visual-replicator/references/acceptance.md`
- Test: `tests/test_skill_package.py`

- [ ] Write `test_skill_package.py` first. Assert exact Skill name, trigger description, required reference links, required workflow commands, and the prohibition on content rewriting.
- [ ] Run `python3 -m unittest tests.test_skill_package -v` and confirm it fails because the package does not exist.
- [ ] Initialize the Skill through `init_skill.py` with `scripts,references` resources and deterministic UI metadata.
- [ ] Replace placeholders with the approved workflow and focused references.
- [ ] Run the unit test and `quick_validate.py`; require both to pass.
- [ ] Commit the package skeleton and references.

### Task 2: Inspect PPTX inputs into a source ledger

**Files:**
- Create: `skills/ppt-visual-replicator/scripts/pptx_inspect.py`
- Test: `tests/test_pptx_inspect.py`

- [ ] Write a failing test that creates a minimal OOXML fixture with four slides and asserts canvas size, ordered slide numbers, text blocks, picture/table/chart counts, family hints, SHA-256, and critical numeric tokens.
- [ ] Run the test and confirm failure because `pptx_inspect.py` does not exist.
- [ ] Implement standard-library ZIP/XML inspection. Reject `.~` lock files, missing presentation parts, and non-PPTX inputs with actionable errors.
- [ ] Run the focused test and the full suite.
- [ ] Commit the inspector.

### Task 3: Prepare a visual run and deterministic page map

**Files:**
- Create: `skills/ppt-visual-replicator/scripts/prepare_visual_run.py`
- Create: `skills/ppt-visual-replicator/scripts/build_visual_plan.py`
- Test: `tests/test_visual_plan.py`

- [ ] Write failing tests for run-directory creation, relative manifest paths, page-family classification, same-family matching, closest-signature matching, and explicit mapping overrides.
- [ ] Confirm the tests fail for missing modules.
- [ ] Implement `prepare_visual_run.py` to create the run contract and ledgers without overwriting existing runs. Add `--skip-render` for deterministic offline tests and emit exact renderer commands when rendering is deferred.
- [ ] Implement `build_visual_plan.py` with generic family/signature scoring and optional JSON overrides.
- [ ] Run focused and full tests.
- [ ] Commit run preparation and visual planning.

### Task 4: Build serial image-edit jobs

**Files:**
- Create: `skills/ppt-visual-replicator/scripts/build_image_jobs.py`
- Create: `skills/ppt-visual-replicator/references/image-prompt-contract.md`
- Test: `tests/test_image_jobs.py`

- [ ] Write failing tests that assert one job per target page, target image first, reference image second, prompt/output hashes, deterministic command arguments, serial execution order, and refusal to overwrite outputs without `--force`.
- [ ] Confirm tests fail because job generation is missing.
- [ ] Implement prompt and job generation. Default to dry-run manifest creation; execute only with `--execute` and call `editppt image edit` one page at a time.
- [ ] Run focused and full tests.
- [ ] Commit image-job orchestration.

### Task 5: Validate generated pages and reconstructed PPTX

**Files:**
- Create: `skills/ppt-visual-replicator/scripts/validate_visual_run.py`
- Test: `tests/test_validate_visual_run.py`

- [ ] Write failing tests for missing generated pages, invalid image dimensions, source/final slide-count mismatch, missing critical numeric tokens, image-only final slides, missing reconstruction validation, and a passing editable result.
- [ ] Confirm tests fail because validation is missing.
- [ ] Implement validation by reading image headers, the source ledger, final PPTX OOXML, and `editppt` validation JSON. Emit one machine-readable `validation.json` with `passed`, `errors`, `warnings`, and evidence counters.
- [ ] Run focused and full tests.
- [ ] Commit final validation.

### Task 6: Prove the four-page and historical regression paths

**Files:**
- Create: `tests/fixtures/README.txt` only if a fixture-generation note is required; do not copy customer artifacts.
- Modify: `tests/test_visual_plan.py`
- Modify: `tests/test_validate_visual_run.py`

- [ ] Generate the four-page synthetic fixture entirely inside test temporary directories and run prepare → plan → image-job dry run → validation failure before reconstruction.
- [ ] Run the validator against four representative recorded pages from the existing 13-page run through an environment-provided external fixture path; skip cleanly when that path is absent.
- [ ] Run `editppt doctor` and confirm the runtime is ready.
- [ ] Run all unit tests, `quick_validate.py`, placeholder scans, and Git diff review.
- [ ] Commit the integration proof and final Skill package.

