# validate extraction JSON against the graphify schema before graph assembly
from __future__ import annotations

# Canonical file types with dedicated Obsidian tags / panel semantics.
# NOT a strict allowlist — semantic extractors (LLM subagents) routinely emit
# richer, domain-useful types (concept, decision, entity, technology, normativa,
# component, infrastructure...). Those are accepted as-is by the file_type check
# below; this set only documents the well-known types and drives known-type tagging.
KNOWN_FILE_TYPES = {
    "code", "document", "paper", "image", "rationale",
    "concept", "decision", "entity", "technology",
}
VALID_FILE_TYPES = KNOWN_FILE_TYPES  # backward-compat alias
VALID_CONFIDENCES = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
REQUIRED_NODE_FIELDS = {"id", "label", "file_type", "source_file"}
REQUIRED_EDGE_FIELDS = {"source", "target", "relation", "confidence", "source_file"}


def validate_extraction(data: dict) -> list[str]:
    """
    Validate an extraction JSON dict against the graphify schema.
    Returns a list of error strings - empty list means valid.
    """
    if not isinstance(data, dict):
        return ["Extraction must be a JSON object"]

    errors: list[str] = []

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
            if "file_type" in node:
                ft = node["file_type"]
                # Accept any non-empty string. LLM extractors produce useful
                # domain types beyond the canonical set; rejecting them would
                # discard real semantic signal. Only a missing/blank/non-string
                # file_type is an actual error.
                if not isinstance(ft, str) or not ft.strip():
                    errors.append(
                        f"Node {i} (id={node.get('id', '?')!r}) has invalid file_type "
                        f"{ft!r} - must be a non-empty string"
                    )

    # Edges
    if "edges" not in data:
        errors.append("Missing required key 'edges'")
    elif not isinstance(data["edges"], list):
        errors.append("'edges' must be a list")
    else:
        node_ids = {n["id"] for n in data.get("nodes", []) if isinstance(n, dict) and "id" in n}
        for i, edge in enumerate(data["edges"]):
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
            if "source" in edge and node_ids and edge["source"] not in node_ids:
                errors.append(f"Edge {i} source '{edge['source']}' does not match any node id")
            if "target" in edge and node_ids and edge["target"] not in node_ids:
                errors.append(f"Edge {i} target '{edge['target']}' does not match any node id")

    return errors


def assert_valid(data: dict) -> None:
    """Raise ValueError with all errors if extraction is invalid."""
    errors = validate_extraction(data)
    if errors:
        msg = f"Extraction JSON has {len(errors)} error(s):\n" + "\n".join(f"  • {e}" for e in errors)
        raise ValueError(msg)
