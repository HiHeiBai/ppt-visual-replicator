# Acceptance Rules

## Generated stage

- One generated image exists for every planned target page.
- Every image has the expected aspect ratio and non-zero dimensions.
- Every job records target, reference, prompt, and output provenance.
- No page is marked failed or left pending.

## Final editable stage

- Final slide count matches the selected target slide count.
- `editppt` final validation reports `passed: true` with no failed pages.
- Required source text and critical numeric tokens are present.
- Each non-empty slide contains editable text or structural objects; a single full-slide image is not acceptable.
- Complex charts, paper screenshots, and scientific illustrations may remain independent image objects.
- Final rendering has no clipping, overflow, broken relationships, or missing media.

## Delivery

Return the final PPTX path, run directory, and validation path. Report warnings plainly; do not describe a warning as a pass.

