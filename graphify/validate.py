# validate extraction JSON against the graphify schema before graph assembly
from __future__ import annotations

# Core file types the graph always accepts — emitted by v8's own extractors
# (doc_ref = RFC / doc references detected in code, kept so they aren't collapsed
# to concept). Domain types (decision, normativa, technology, ...) are NO LONGER
# hardcoded here: each project declares its own in a `.graphify-types` file at its
# root (see detect.load_project_file_types). The effective allowlist a build uses
# is BASE_FILE_TYPES | that project set — every value stays a safe slug (no
# export-tag injection), and anything outside the effective set collapses to
# "concept" in build.py rather than fragmenting the type space on LLM typos.
BASE_FILE_TYPES = frozenset({
    "code", "document", "paper", "image", "rationale", "concept", "doc_ref",
})
# Backward-compat alias for modules/tests that import the old name. Now base-only;
# callers that want the project's domain types must pass them via ``valid_types``.
VALID_FILE_TYPES = BASE_FILE_TYPES
VALID_CONFIDENCES = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
REQUIRED_NODE_FIELDS = {"id", "label", "file_type", "source_file"}
REQUIRED_EDGE_FIELDS = {"source", "target", "relation", "confidence", "source_file"}


def validate_extraction(
    data: dict, valid_types: frozenset[str] | None = None
) -> list[str]:
    """
    Validate an extraction JSON dict against the graphify schema.
    Returns a list of error strings - empty list means valid.

    valid_types: the effective file_type allowlist for this build. When None,
    falls back to BASE_FILE_TYPES (core types only) — callers that know the
    project root pass ``BASE_FILE_TYPES | load_project_file_types(root)`` so the
    project's `.graphify-types` domain types validate too.
    """
    if not isinstance(data, dict):
        return ["Extraction must be a JSON object"]

    valid = valid_types if valid_types is not None else BASE_FILE_TYPES
    errors: list[str] = []

    # Collected during the node pass so the edge pass can reuse it. Only
    # hashable ids land here; a non-hashable id (e.g. a list emitted by a
    # malformed LLM extraction) is reported as an error rather than crashing
    # the validator on set construction.
    node_ids: set = set()

    # Nodes
    if "nodes" not in data:
        errors.append("Missing required key 'nodes'")
    elif not isinstance(data["nodes"], list):
        errors.append("'nodes' must be a list")
    else:
        for i, node in enumerate(data["nodes"]):
            if not isinstance(node, dict):
                errors.append(f"Node {i} must be an object")
                continue
            for field in REQUIRED_NODE_FIELDS:
                if field not in node:
                    errors.append(f"Node {i} (id={node.get('id', '?')!r}) missing required field '{field}'")
            if "id" in node:
                try:
                    hash(node["id"])
                except TypeError:
                    errors.append(
                        f"Node {i} has non-hashable id {node['id']!r} - id must be a string"
                    )
                else:
                    node_ids.add(node["id"])
            # file_type must be one of the effective types (BASE_FILE_TYPES plus
            # the project's `.graphify-types` domain layer, threaded in via
            # ``valid_types``); genuine typos/junk are still reported here and
            # collapsed to "concept" by build.py, keeping the type space clean.
            # Guard the membership test with isinstance: a list/dict file_type
            # (malformed extraction) is unhashable and would crash `in valid`.
            if "file_type" in node:
                _ft = node["file_type"]
                if not isinstance(_ft, str) or _ft not in valid:
                    errors.append(
                        f"Node {i} (id={node.get('id', '?')!r}) has invalid file_type "
                        f"{_ft!r} - must be one of {sorted(valid)}"
                    )

    # Edges - accept "links" (NetworkX <= 3.1) as fallback for "edges"
    edge_list = data.get("edges") if "edges" in data else data.get("links")
    if edge_list is None:
        errors.append("Missing required key 'edges'")
    elif not isinstance(edge_list, list):
        errors.append("'edges' must be a list")
    else:
        for i, edge in enumerate(edge_list):
            if not isinstance(edge, dict):
                errors.append(f"Edge {i} must be an object")
                continue
            for field in REQUIRED_EDGE_FIELDS:
                if field not in edge:
                    errors.append(f"Edge {i} missing required field '{field}'")
            if "confidence" in edge and edge["confidence"] not in VALID_CONFIDENCES:
                errors.append(
                    f"Edge {i} has invalid confidence '{edge['confidence']}' "
                    f"- must be one of {sorted(VALID_CONFIDENCES)}"
                )
            for endpoint in ("source", "target"):
                if endpoint not in edge:
                    continue
                val = edge[endpoint]
                try:
                    unmatched = bool(node_ids) and val not in node_ids
                except TypeError:
                    errors.append(
                        f"Edge {i} {endpoint} {val!r} is non-hashable - must be a string"
                    )
                    continue
                if unmatched:
                    errors.append(f"Edge {i} {endpoint} '{val}' does not match any node id")

    return errors


def assert_valid(data: dict, valid_types: frozenset[str] | None = None) -> None:
    """Raise ValueError with all errors if extraction is invalid."""
    errors = validate_extraction(data, valid_types=valid_types)
    if errors:
        msg = f"Extraction JSON has {len(errors)} error(s):\n" + "\n".join(f"  • {e}" for e in errors)
        raise ValueError(msg)
