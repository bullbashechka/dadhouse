# Repository Guidelines

## Project Structure & Module Organization

This workspace contains an architectural Blender project for a family house, roof alternatives, and an open mezzanine.

- `PRD.md`: authoritative project requirements and delivery sequence, written in Russian.
- Root PDF (`ЭП Жилой дом Ул.Ынтымак, 12 Солнечный 2-1.pdf`): source drawings; PDF page 2 contains the floor plan, page 1 the elevations, and page 3 the sections and roof plan.
- Root PNG files: architectural and mezzanine references. Preserve their original filenames.
- `.agents/skills/archviz/` and `.agents/skills/blender-production/`: modeling workflows.
- `skills-lock.json`: installed skill provenance.

There are currently no source-code, test, or generated-model directories. When adding deliverables, use clearly named folders such as `models/`, `renders/`, and `scripts/`.

## Build, Test, and Development Commands

No build system, package manager, automated tests, or repository-specific commands are configured. Work on scenes in Blender and save editable `.blend` files. Document exact commands and prerequisites alongside any future automation; do not assume `npm test` or `make build` exists.

## Modeling Style & Naming Conventions

Use real-world scale with meters as scene units; convert drawing dimensions from millimeters explicitly. Organize collections by base house, roof variants, mezzanines, stairs, furniture, lighting, and cameras. Use descriptive names such as `Roof_Gable` and `Camera_Exterior_Front`.

Keep alternatives independently switchable. Preserve the base layout and ground-floor openings according to `PRD.md`. Use consistent cameras, lighting, and neutral materials for comparisons. If adding Python scripts, use four-space indentation and `snake_case` identifiers; no formatter or linter is configured.

## Validation Guidelines

Validation is geometric and visual; no coverage target applies. Check dimensions against the PDF, normals, intersections, openings, stair access, and continuous mezzanine headroom. Include structural thicknesses in clearance checks. Reopen deliverable scenes, verify resources resolve, and inspect rendered comparisons and dimensioned sections.

## Test-Driven Development (TDD)

Use the Red → Green → Refactor cycle for new behavior and bug fixes in modeling scripts, automation, and geometric validation:

1. **Red:** Before implementation, write the smallest meaningful test for the required behavior or a regression test reproducing the defect. Run it and confirm it fails for the expected reason, rather than because of a broken environment or missing dependency.
2. **Green:** Implement the smallest change that satisfies the requirement and makes the test pass. Derive expected values from `PRD.md`, source drawing dimensions, or explicitly recorded assumptions; do not copy the implementation's calculations into the test.
3. **Refactor:** Improve structure without changing behavior, then rerun the relevant tests. Keep each cycle focused on one requirement.

For Blender geometry, define measurable acceptance checks before changing the scene: units and dimensions, preserved openings, independent variant switching, and continuous route clearance including structural thicknesses. Automate repeatable checks where practical; verify the resulting geometry rather than only object names or script completion. Use documented tolerances and test boundary cases for clearance constraints.

When a requirement needs visual inspection, record the expected result and a repeatable inspection procedure before modeling, then compare the result against those criteria. Manual visual checks complement automated tests and must not be reported as automated TDD. Do not create tests for documentation-only or reversible, low-impact edits, or tests that merely mirror implementation details.

Keep future automated tests in `tests/` and document their prerequisites and exact execution commands. After a change, run the affected checks and relevant regression tests; report what passed, failed, or could not be run. TDD does not authorize modeling or rendering before the explicit start instruction required by `PRD.md`.

## Commit & Pull Request Guidelines

This directory has no Git metadata or commit history. If version control is introduced, use concise imperative messages, for example `Add baseline house geometry`. Describe changed variants, requirements addressed, assumptions, and validation performed. Attach comparison renders for visual changes.

## Agent-Specific Instructions

Read `PRD.md` before implementation. Modeling and rendering require a separate explicit instruction to begin, as specified in the PRD. Preserve source references and record unresolved dimensions as assumptions.

### Blender and Architectural Visualization Skills

- Read and apply [blender-production](.agents/skills/blender-production/SKILL.md) before creating, modifying, inspecting, rendering, or delivering Blender scenes. Use it for scene control, repeatable modeling, geometric and visual checks, and verification of saved deliverables.
- Additionally read and apply [archviz](.agents/skills/archviz/SKILL.md) for architectural modeling and interior/exterior visualization. Use it for real-world scale, architectural cameras, materials, and lighting.
- For this house project, use both skills together when implementing models or architectural renders. Read their supporting references only as needed for the current task.
- Skills guide execution; they do not authorize starting implementation. Follow the project scope and delivery sequence in `PRD.md` and the user's explicit instructions.
