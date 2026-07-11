# PPT Visual Style Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent later generated slides from drifting into different layout systems by locking one primary reference deck, one reference anchor per page family, and one approved generated calibration anchor per family.

**Architecture:** Change visual planning from independent per-page nearest-neighbor matching to deck-level primary-reference and family-anchor selection. Split image generation into calibration and scale phases; scale jobs include the approved generated family page as a third image. Extend generated-stage validation to reject unlocked or unapproved runs.

**Tech Stack:** Python 3 standard library, `unittest`, existing `editppt image edit` command surface.

---

### Task 1: Lock the primary reference deck and family anchors

**Files:**
- Modify: `skills/ppt-visual-replicator/scripts/build_visual_plan.py`
- Modify: `skills/ppt-visual-replicator/references/page-matching.md`
- Test: `tests/test_visual_plan.py`

- [x] Add a failing test with three reference decks and verify default mappings use reference index 0 only.
- [x] Add a failing test with multiple content candidates and verify all target content pages reuse one canonical anchor.
- [x] Add a failing test proving fallback decks require `allow_fallback_decks=True`.
- [x] Implement primary-deck locking, deterministic family medoids, explicit fallback warnings, and style-lock metadata.
- [x] Run focused and full tests, then commit.

### Task 2: Add calibration-first image generation

**Files:**
- Modify: `skills/ppt-visual-replicator/scripts/build_image_jobs.py`
- Modify: `skills/ppt-visual-replicator/references/image-prompt-contract.md`
- Test: `tests/test_image_jobs.py`

- [x] Add a failing test that marks the first target page in every family as `calibration` and remaining pages as `scale`.
- [x] Add a failing test that calibration execution writes output hashes while scale execution is refused before approval.
- [x] Add a failing test that scale commands pass target, family reference, then approved generated calibration image.
- [x] Implement phase execution and `calibration-approved.json` hash recording.
- [x] Run focused and full tests, then commit.

### Task 3: Reject deck-level inconsistency before reconstruction

**Files:**
- Modify: `skills/ppt-visual-replicator/scripts/validate_visual_run.py`
- Modify: `skills/ppt-visual-replicator/references/acceptance.md`
- Test: `tests/test_validate_visual_run.py`

- [x] Add failing tests for multiple automatic decks, multiple automatic anchors per family, missing calibration approval, and changed calibration hashes.
- [x] Implement consistency evidence and errors in generated-stage validation.
- [x] Run focused and full tests, then commit.

### Task 4: Update the Skill workflow and verify the real 47-page plan

**Files:**
- Modify: `skills/ppt-visual-replicator/SKILL.md`
- Modify: `tests/test_skill_package.py`

- [x] Add failing package assertions for primary deck lock, calibration execution, approval, scale execution, and consistency validation.
- [x] Update the workflow commands and stop conditions without duplicating reference details.
- [x] Verify the real 47-page target uses one primary deck and at most one automatic anchor per family.
- [x] Run all tests, `quick_validate.py`, placeholder scans, `editppt doctor`, and Git diff checks.
- [x] Commit the completed optimization.
