# Acceptance Rules

## Direct redraw

- One selected target slide and one selected reference slide exist and render at the expected aspect ratio.
- The generated slide has one recorded target and reference input, one prompt, and one output image.
- The generated slide retains target claims, numbers, charts, tables, citations, page markers, and document codes; it does not copy reference wording, facts, logos, or identifiers.
- The generated slide visibly adopts the reference palette, typography character, spacing, decorative language, and hierarchy.

## Editable PPT

- `editppt` page validation passes and the final PPTX opens.
- Required text and critical numeric tokens from the target are present as editable objects where practical.
- The editable preview remains visually faithful to the generated slide; structural validation alone is not enough.
- Complex charts, paper screenshots, and scientific illustrations may remain independent image objects.

## Delivery

Return the final PPTX path and the direct run directory. Report warnings plainly; do not call a warning a pass.
