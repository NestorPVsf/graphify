# Capa 1 — Project-configurable domain file_types (`.graphify-types`)

## Goal
Replace the hardcoded fork file_types in `graphify/validate.py` (`VALID_FILE_TYPES`)
with a **per-project** config file. Each project declares its own domain types;
the core stays generic. This removes Gaea-specific types from generic code.

## Current state (commits 4ca88d6, da80965, eea98f0 on branch v8-migration)
`graphify/validate.py` `VALID_FILE_TYPES` currently = 13 hardcoded:
- 7 core: `code, document, paper, image, rationale, concept, doc_ref`
- 6 fork (Gaea-specific — REMOVE from the hardcode): `decision, normativa,
  technology, component, infrastructure, entity`

Three places consume the allowlist — trace and thread the effective set through all:
1. `graphify/validate.py` `validate_extraction(data)` — reports invalid file_type
   (note: it already guards `isinstance(_ft, str)` before the membership test —
   keep that guard).
2. `graphify/build.py` normalization (~L415):
   `if ft not in VALID_FILE_TYPES: node["file_type"] = _FILE_TYPE_SYNONYMS.get(ft, "concept")`
3. `graphify/semantic_cleanup.py` `validate_semantic_fragment()` uses
   `VALID_SEMANTIC_FILE_TYPES = frozenset(VALID_FILE_TYPES)`.

## Design

### Config file
`.graphify-types` at project root (sibling of `.graphifyignore`). Format:
- one type slug per line, matching `^[a-z][a-z0-9_-]{0,63}$` (safe slug — this is
  what prevents export-tag YAML injection).
- `#` comments and blank lines ignored.
- invalid slugs skipped with a single stderr warning (never crash).

### Constants
- `BASE_FILE_TYPES = frozenset({"code","document","paper","image","rationale","concept","doc_ref"})`
  — always valid, not configurable. Define in `validate.py`.
- Remove the 6 fork types from the hardcode. `VALID_FILE_TYPES` becomes `BASE_FILE_TYPES`
  (keep the name as an alias if other modules import it, but it now = base only).

### Loader
`load_project_file_types(root: Path) -> frozenset[str]` — reads `.graphify-types`,
validates each slug against the regex, returns the set (empty if file missing).
Put it near `_load_graphifyignore` in `graphify/detect.py` (same discovery pattern).
Cheap per-call read is fine; cache per-root only if a hot path needs it.

**Effective allowlist = `BASE_FILE_TYPES | load_project_file_types(root)`.**

### Propagation (the core of the work — trace the callers)
`validate_extraction` and `validate_semantic_fragment` are pure (no root). Pick ONE
clean approach and apply consistently:
- **Preferred**: add optional param `valid_types: frozenset[str] | None = None` to
  both; when `None`, fall back to `BASE_FILE_TYPES`. Callers that know the project
  root load the effective set and pass it.
- `build.py` normalization DOES know the root (watch_path / project root in the
  rebuild path) — load the effective set there and use it instead of the global.

Trace EVERY caller of `validate_extraction` / `validate_semantic_fragment` / the
build normalization and thread the effective types through. Backward-compat:
no root available → `BASE_FILE_TYPES` only.

### Extraction prompt (so the LLM EMITS custom types)
The semantic extraction prompt (`graphify/skill-*.md` templates and/or
`graphify/llm.py`) lists ~6 generic file_types. Inject the project's
`.graphify-types` into that prompt so subagents emit them. Minimal, additive —
do not rewrite the templates, just add the project types when present.

### Gaea config
Create `D:\Proyectos\Profesionales\Gaea-Legal\.graphify-types` with the 5 real
types (verify against its graph.json): `decision, normativa, technology,
component, infrastructure`. (`entity` was a generic add-on — include only if the
graph actually uses it.)

### Tests
- Update existing fork-type tests (`test_build.py::test_fork_semantic_types_preserved`,
  `test_validate.py::test_fork_semantic_type_is_valid`) to the new model: a fork
  type is valid only when passed via `valid_types` (or a fixture `.graphify-types`).
- Add: loader parses/validates slugs; unknown slug skipped; no file → base only;
  configured project type passes validation; injection-unsafe slug rejected.
- Keep the 3 upstream tests green (`weird_type`→concept, `video` invalid,
  `pattern`→concept) and the unhashable-file_type regression test.

## Verification
- Run pytest against THIS worktree without touching production: use the venv python
  `C:\Users\rotse\graphify-v8-testenv\Scripts\python.exe` (has deps + pytest) with
  `PYTHONPATH=C:/Users/rotse/graphify-v8-custom-types` so `import graphify` resolves
  here, NOT to the production editable install (which points to graphify-v8-migration).
- Rebuild over Gaea real (with its new `.graphify-types`) must still preserve the
  30 custom nodes — run it the same way (PYTHONPATH to this worktree), and copy
  Gaea's graph to a sandbox first so the real one isn't modified.
- A project WITHOUT `.graphify-types` collapses non-base types to `concept`.

## Constraints
- Work ONLY in `graphify-v8-custom-types` (branch `v8-custom-types`). Do NOT touch
  `graphify-v8-migration` (production) or its editable install.
- Backward compatible. Security: validate project types against the slug regex.
- Do not change `_reconcile` preservation logic (node preservation is type-agnostic).
- Commit on `v8-custom-types` with conventional messages. Do NOT push.

---

## STATUS (2026-07-15)

**DONE** (commits 509311d, 180bcd2, f6ff33d on v8-custom-types):
- detect.py: `load_project_file_types()` loader (safe-slug validated, warns + skips bad slugs).
- validate.py: `BASE_FILE_TYPES` (7 core); `VALID_FILE_TYPES` = base alias; `valid_types` param on `validate_extraction`; isinstance guard kept.
- build.py: `build_from_json` computes effective allowlist = BASE | project types (loaded from `root`), used in both normalization and `validate_extraction`.
- semantic_cleanup.py: `validate_semantic_fragment` / `load_validated_semantic_fragment` take `valid_types`.
- Root threaded into ALL Python `build_from_json` callers: watch.py `_rebuild_code` + cli.py recluster (were missing it — the bug that collapsed types); build.py + diagnostics.py already passed it.
- Gaea `.graphify-types` created (decision/normativa/technology/component/infrastructure).
- Tests: 93 pass (1 preexisting Windows failure, unrelated). Loader + preserve-with-config + collapse-without-config covered.
- **VERIFIED**: rebuild over Gaea's real graph preserves 30/30 custom nodes WITH `.graphify-types`, collapses them to concept WITHOUT it. The critical production flow (post-commit hook `_rebuild_code`) is correct.

**PENDING** (remate — the LLM *generation* path, lower risk; preservation already works):
- skill-*.md extraction templates: some pass `root='INPUT_PATH'` to `build_from_json`, some (aider, devin) pass only `directed=`. For the LLM to GENERATE new domain-typed nodes, the active skill's extraction code should (a) pass root, (b) load `.graphify-types` and pass `valid_types` to `load_validated_semantic_fragment`, (c) inject the project types into the emit prompt.
- 2nd opinion (Codex read-only / cx-reviewer) before merging to v8-migration (production).
- Merge v8-custom-types -> v8-migration + push; then production honors `.graphify-types`.
- Update PVSF skill counters (graphify moved to always-on).
