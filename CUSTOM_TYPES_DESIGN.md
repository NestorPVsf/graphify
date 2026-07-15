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

## STATUS (2026-07-15) — CAPA 1 SHIPPED TO PRODUCTION

**DONE — backend (509311d, 180bcd2, f6ff33d) + critical fix (278759d), MERGED to `v8-migration` + pushed:**
- detect.py: `load_project_file_types()` loader (safe-slug validated, warns + skips bad slugs; reads `utf-8-sig` so a Windows BOM doesn't drop the first slug).
- validate.py: `BASE_FILE_TYPES` (7 core); `VALID_FILE_TYPES` = base alias; `valid_types` param on `validate_extraction`; isinstance guard kept.
- build.py: effective allowlist = BASE | project types (loaded from `root`); isinstance guard so a non-string file_type degrades to "concept" instead of crashing the membership test.
- semantic_cleanup.py: `validate_semantic_fragment` / `load_validated_semantic_fragment` take `valid_types`; same isinstance guard.
- Root threaded into ALL Python `build_from_json` callers: watch.py `_rebuild_code` + cli.py recluster.
- **cli.py `cluster-only`/`label` FIX — data-loss bug found by the Codex 2nd opinion, NOT by the design or prior review**: `--graph <other>/graphify-out/graph.json` derived the build root from `watch_path` (cwd), so an external project's `.graphify-types` was never found → its domain types collapsed to "concept" AND `to_json` overwrote the external graph.json (blast radius: the Gaea use-case itself). Now derives the root via `_infer_merge_root(graph_json)`, sharing the `_external_graph` condition with the `out` derivation. Regression test in test_cli_export.py (fails without the fix, passes with it).
- Gaea `.graphify-types` created (decision/normativa/technology/component/infrastructure).
- Tests: 2989 pass, 0 new regressions (31 preexisting failures unrelated: terraform/ollama/etc.; 1 preexisting Windows `os.geteuid` skip).
- **VERIFIED**: rebuild over Gaea's real graph preserves 30/30 custom nodes; the external-graph recluster scenario (the data-loss bug) preserves types — no collapse, no overwrite.

**2nd opinion**: DONE — Codex `gpt-5.6-sol` xhigh, read-only → NO-GO on the cli.py data-loss bug (now fixed) + 5 minor findings. Scope "unblock + cheap hardening" applied.
**Merge**: DONE — fast-forward `v8-custom-types` → `v8-migration` (278759d) + push to origin. Production honors `.graphify-types`.
**PVSF counters**: DONE — `graphify` skill moved to always-on (43/59).

**CAPA 2 — LLM *generation* path = DEFERRED to a design session (NOT mechanical).** For the LLM to EMIT custom types, the skillgen extraction prompt must change — but that prompt (`tools/skillgen/fragments/references/shared/extraction-spec.md`) states *"file_type MUST be one of exactly these six values... any other rejected"* and is a SHARED/static fragment guarded by CI (`--schema-singleton`, `--monolith-roundtrip` for aider/devin monoliths, `--check` over 134 artifacts). Reconciling per-project custom types with the enum-singleton design needs deliberate design:
- (a) how a generic/shared prompt instructs the LLM to read `.graphify-types` at runtime without breaking the singleton;
- (b) thread root into aider/devin `build_from_json` (low-risk, already sanctioned by `_is_directed_fix_line`) — verify the INPUT_PATH substitution machinery exists in the monoliths first;
- (c) pass `valid_types` to `load_validated_semantic_fragment` (skill-devin.md:351 calls it without them → a domain-typed chunk is rejected and dropped);
- (d) add sanction predicates to gen.py + re-bless `expected/` + run the 5 guards + tests/test_skillgen.py.

**Follow-ups (out of scope, tracked separately):**
- export.py: escape file_type in `export obsidian --graph` (loads JSON raw via node_link_graph, bypasses build_from_json normalization → Markdown/HTML injection into the Obsidian vault). Medium.
- detect.py loader hardening: size cap (256 KiB) / symlink refusal / warning cap. Low. (A codex process wrote this during the fix session; reverted as out-of-scope, being done deliberately in its own task.)

**Harness incidents (2026-07-15, not graphify code, under separate review):** (1) a permission-DENIED `codex exec` wrote out-of-scope changes anyway in the background; (2) API keys appear in plaintext in the bash-wrapper commandline.
