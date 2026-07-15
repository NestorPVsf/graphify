# Capa 2 — LLM *generation* of project-configurable domain file_types

Sequel to `CUSTOM_TYPES_DESIGN.md` (Capa 1, DONE + merged to v8-migration). Capa 1
made the runtime (`graphify/`) **preserve** domain types declared in a project's
`.graphify-types`. This Capa 2 makes the extraction **prompt** instruct the LLM to
**emit** those domain types for new content, without breaking skillgen's CI guards.

Scope is `tools/skillgen/fragments/**` (the human-edited source of truth) plus one
new sanction predicate in `tools/skillgen/gen.py`. Nothing in `graphify/` runtime
changes — Capa 1 already threads `root` / `valid_types` through the Python side.

---

## Design decision (locked): inject a `PROJECT_TYPES` placeholder

The extraction prompt is static, shared, and generic; it cannot bake per-project
types at gen time. Two ways to make a static prompt admit per-project types:

- **(rejected) read-at-runtime**: tell each subagent "read `.graphify-types` and add
  its slugs to the enum." Relies on per-subagent obedience to a secondary file read
  buried in a large prompt → non-deterministic; contradicts graphify's deterministic/
  auditable promise.
- **(chosen) inject**: the orchestrator resolves `.graphify-types` **once** and
  substitutes a `PROJECT_TYPES` clause into every extraction prompt, exactly like the
  existing `FILE_LIST` / `INPUT_PATH` / `DEEP_MODE` substitution contract. The model is
  *told* the valid types in-context — strictly more robust, and idiomatic with the
  machinery that already exists.

### The placeholder holds the *entire optional clause*

So the sentence stays grammatical whether or not the project declares types, and so
the six-value `ENUM_PROSE` stays byte-verbatim on the line (keeps `schema-singleton`
and the monolith `_is_enum_line` sanction green):

- Enum sentence becomes (all four prompt sites, adapt to local wording):
  `` `file_type` must be one of the six base values — `code`, `document`, `paper`, `image`, `rationale`, `concept`PROJECT_TYPES. A value outside the allowed set is invalid and will be rejected. ``
- `PROJECT_TYPES` resolves to:
  - **absent/empty `.graphify-types`** → `` `` (empty string) → sentence reads
    "...`concept`. A value outside..." = base-six only (backward-compatible).
  - **present** → `` — or one of this project's domain types: decision, normativa, technology `` (leading em-dash + space), comma-joined slugs from `.graphify-types`.

Resolution rule (given to the orchestrator/agent, verbatim in prose): "Read
`.graphify-types` at INPUT_PATH (one slug per line; skip blank lines and `#`
comments). If it has slugs, `PROJECT_TYPES` = ' — or one of this project's domain
types: ' + the comma-joined slugs; otherwise `PROJECT_TYPES` is empty. Substitute it
into the schema instruction the same way you substitute INPUT_PATH."

`ENUM_PROSE` (`` `code`, `document`, `paper`, `image`, `rationale`, `concept` ``) MUST
remain byte-verbatim and contiguous on the enum line — do not reorder or reword the
base list. Only append the `PROJECT_TYPES` placeholder after `` `concept` `` and
rephrase the trailing "MUST be one of exactly these six values / any other value is
invalid" wording. This is what keeps `schema-singleton` and `_is_enum_line` happy.

---

## What each platform needs (asymmetries — verified against the tree)

| Concern | split (13) | aider (monolith) | devin (monolith) |
|---|---|---|---|
| Prompt emits domain types (a) | **yes** — edit shared spec | **yes** — edit inline | **yes** — edit inline |
| `root` on `build_from_json` (b) | already done (Capa 1) | **add** | **add** |
| per-chunk `valid_types` (c) | n/a (Part C raw-merges) | n/a (raw accumulate) | **add** |

- **split**: Part C raw-merges chunk JSON, then `build_from_json(root='INPUT_PATH')`
  (Capa 1) preserves domain types. So split needs **only the prompt change** — nothing
  else. Verified: `core.md` Steps 4/5 already pass `root='INPUT_PATH'`.
- **aider**: sequential single-agent, raw accumulation, no per-chunk validation. Needs
  prompt change + `root` threading. No `valid_types` (it never calls
  `load_validated_semantic_fragment`).
- **devin**: subagent dispatch + **per-chunk** `load_validated_semantic_fragment(Path(c))`
  with no `valid_types` → a single domain-typed node makes `errors` truthy and the whole
  chunk is `continue`-skipped. Needs prompt change + `root` threading + `valid_types`.

INPUT_PATH substitution machinery is confirmed present in both monoliths
(`detect(Path('INPUT_PATH'))`, `save_manifest(..., root='INPUT_PATH')`,
`generate(..., 'INPUT_PATH', ...)`, `python3 -m graphify.watch INPUT_PATH`), so (b)/(c)
can reuse it.

---

## Edits — file by file

All paths under `tools/skillgen/fragments/` unless noted. Read the current text first;
line numbers are as of this writing and may drift.

### 1. `references/shared/extraction-spec.md` (verbose)
- **Header (~L3)**: add `PROJECT_TYPES` to the substitution list and append the
  resolution rule sentence (above). New list: "substitute FILE_LIST, CHUNK_NUM,
  TOTAL_CHUNKS, DEEP_MODE, CHUNK_PATH, and PROJECT_TYPES."
- **Enum sentence (~L19)**: replace "`file_type` MUST be one of exactly these six
  values: `code`, `document`, `paper`, `image`, `rationale`, `concept`. Any other value
  is invalid and will be rejected." with the new enum sentence (base six + `PROJECT_TYPES`
  clause + "A value outside the allowed set is invalid and will be rejected"). Keep
  everything else on that line (the `` file_type:"rationale" `` guidance) intact.

### 2. `references/shared/extraction-spec-compact.md` (compact)
- **Header (~L3)**: add `PROJECT_TYPES` to the substitution list.
- **Enum sentence (~L17)**: same rewrite as verbose.

### 3. `core/core.md` (shared by all 13 split platforms — ONE edit covers all)
- In **Step 3 Part B**, before the dispatch (`@@DISPATCH@@`), add a short instruction
  block: read `.graphify-types` at INPUT_PATH, build the `PROJECT_TYPES` clause per the
  resolution rule, and substitute it into every subagent prompt (like DEEP_MODE — it is
  run-level, same for every chunk). One paragraph; no bash required (the agent reads a
  tiny file). Keep it minimal and additive.

### 4. `dispatch/*.md` (all 7)
- Each has a sentence enumerating the substitution tokens ("...with FILE_LIST,
  CHUNK_NUM, TOTAL_CHUNKS, DEEP_MODE, and CHUNK_PATH substituted"). Add `PROJECT_TYPES`
  to that enumeration in every dispatch fragment, so no orchestrator leaves the literal
  placeholder in a subagent prompt. (agent-tool-disk, agent-tool-disk-powershell,
  task-tool-disk, task-tool-disk-trae, codex-agenttask, opencode-mention, manual-paste.)

### 5. `core/aider.md` (monolith)
- **Enum line (~L265)**: rewrite as the new enum sentence (keep `ENUM_PROSE` verbatim +
  the `` file_type:"rationale" `` clause; stay ONE line). Add PROJECT_TYPES clause.
- **PROJECT_TYPES resolution**: add one prose line in the Step-3 extraction section
  telling the agent to resolve PROJECT_TYPES from `.graphify-types` at INPUT_PATH (per the
  resolution rule) before extracting.
- **`root` (b)**: thread `root='INPUT_PATH'` into **every** `build_from_json(...)` call
  (grep the fragment — ~11 sites incl. update/cluster sections), matching split
  Steps 4/5. All are pre-sanctioned by `_is_directed_fix_line`.

### 6. `core/devin.md` (monolith)
- Same enum-line rewrite (~L295), PROJECT_TYPES resolution line, and `root` threading on
  every `build_from_json(...)` as aider.
- **`valid_types` (c)** — the Part B3 merge block (~L342-366):
  - Extend the import to also bring the effective-types helpers:
    ```python
    from graphify.detect import load_project_file_types
    from graphify.validate import BASE_FILE_TYPES
    ```
  - Compute the effective set once (before the chunk loop):
    ```python
    valid = BASE_FILE_TYPES | load_project_file_types(Path('INPUT_PATH'))
    ```
  - Pass it to the validator:
    ```python
    d, errors = load_validated_semantic_fragment(Path(c), valid_types=valid)
    ```
  Verified signatures: `load_project_file_types(root: Path) -> frozenset[str]`
  (detect.py:869), `load_validated_semantic_fragment(path, valid_types=None)`
  (semantic_cleanup.py:142), `BASE_FILE_TYPES` (validate.py:12). Substitute INPUT_PATH as
  everywhere else in the monolith.

### 7. `tools/skillgen/gen.py` — new sanction predicate
Add and register in `_SANCTIONED_MONOLITH_DIFFS` (after `_is_directed_fix_line`):

```python
def _is_custom_types_fix_line(line: str) -> bool:
    """Whether a line is part of the project-configurable file_types feature (Capa 2).

    The extraction prompt now admits per-project domain file_types declared in a
    project's ``.graphify-types`` via a ``PROJECT_TYPES`` clause the agent resolves at
    runtime, and devin's per-chunk validation loads that project's effective type set
    so a domain-typed node is not discarded. Both the resolution prose and the Python
    that computes/passes the effective ``valid_types`` are new vs pristine v8 and are
    sanctioned here. Each substring is specific to this feature and absent from the v8
    baseline, so this cannot mask unrelated drift.
    """
    return (
        "PROJECT_TYPES" in line
        or ".graphify-types" in line
        or "load_project_file_types" in line
        or "BASE_FILE_TYPES" in line
        or "valid_types=" in line
        or "load_validated_semantic_fragment(" in line
    )
```

`load_validated_semantic_fragment(` (with paren) is included so the **removed** bare v8
call line is sanctioned too; it matches only the call site, not the unchanged import
line. The enum-line rewrite itself is already covered by the existing `_is_enum_line`
(it keeps `ENUM_PROSE`), so no change there. `build_from_json` `root` threading is
already covered by `_is_directed_fix_line`.

---

## Out of scope (do NOT touch — prevents scope creep)
- `save_semantic_cache(..., allowed_source_files=...)` gets no `root` — that is cache
  portability (#1417-adjacent), unrelated to type generation, and matches split.
- No `graphify/` runtime edits. No changes to `_reconcile` / preservation.
- Do not touch the always-on blocks, hooks, or any non-extraction reference.

---

## Verification (must all pass; use the test venv + worktree PYTHONPATH)

Interpreter for everything: `C:\Users\rotse\graphify-v8-testenv\Scripts\python.exe`,
`PYTHONPATH=C:/Users/rotse/graphify-v8-migration`, cwd = repo root
`C:\Users\rotse\graphify-v8-migration`.

1. **Re-render + re-bless** (fragment edits change committed artifacts):
   `python -m tools.skillgen` then `python -m tools.skillgen --bless`
2. **The 5 guards** (all must print OK, not SKIPPED):
   - `python -m tools.skillgen --check`
   - `python -m tools.skillgen --schema-singleton`
   - `python -m tools.skillgen --monolith-roundtrip`
   - `python -m tools.skillgen --audit-coverage`
   - `python -m tools.skillgen --always-on-roundtrip`
   - **CRITICAL**: `--monolith-roundtrip` / `--audit-coverage` / `--always-on-roundtrip`
     print `SKIPPED: origin/v8 is not fetchable` when the ref is missing — a SKIP is a
     **false green**. First confirm the baseline blob is reachable:
     `git cat-file -e 47042beb05d1f6dd2186c0c499ae2840ce604ead^{commit}` and
     `git rev-parse --verify origin/v8`. If origin/v8 is absent, `git fetch origin v8`
     (or fetch the SHA) so the guards actually run. Report whether they RAN or SKIPPED.
3. **Skillgen tests**: `python -m pytest tests/test_skillgen.py -q`
4. **Runtime tests still green**: `python -m pytest tests/test_build.py tests/test_validate.py -q`
   (the same-tree preservation tests from Capa 1; there is one pre-existing unrelated
   Windows failure — note it, do not "fix" it).
5. **Spot-check a rendered artifact**: confirm `graphify/skill-devin.md` now shows
   `valid_types=valid` in Part B3 and `root='INPUT_PATH'` on its `build_from_json`
   calls, and that `graphify/skill.md` (claude split) + `skill-codex.md` (compact) show
   the `PROJECT_TYPES` clause on the enum line.

## Definition of done
All of §Verification green (guards RAN, not skipped), the diff limited to the files in
§Edits, and a 3-5 line report: what changed, which guards ran vs skipped, test counts,
and one `DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED` label. Do NOT commit or
push — leave the tree dirty for review.
