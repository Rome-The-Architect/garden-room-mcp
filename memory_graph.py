"""memory_graph.py — knowledge-graph memory tools for the Garden Room server.

Same tool API as the official @modelcontextprotocol/server-memory
(create_entities, create_relations, add_observations, delete_*, read_graph,
search_nodes, open_nodes), implemented here so Grok's existing connector
gains memory with no second deploy and no extra cost.

Storage: MEMORY_PATH (default: memory.jsonl next to the room file, e.g.
/data/memory.jsonl on Render) — one JSON object per line:
  {"type": "entity", "name": ..., "entityType": ..., "observations": [...]}
  {"type": "relation", "from": ..., "to": ..., "relationType": ...}

The graph is shared across all of Grok's windows — that IS the point:
a fresh window reads the board and its own past notes in one go.
"""
import json
import os


def _memory_path():
    env = os.environ.get("MEMORY_PATH", "").strip()
    if env:
        return env
    # Default: next to the room file.
    from mcp_server import ROOM_PATH
    return os.path.join(os.path.dirname(ROOM_PATH) or ".", "memory.jsonl")


def _load():
    path = _memory_path()
    entities = {}
    relations = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "entity" and obj.get("name"):
                    entities[obj["name"]] = {
                        "name": obj["name"],
                        "entityType": obj.get("entityType", ""),
                        "observations": list(obj.get("observations", [])),
                    }
                elif obj.get("type") == "relation":
                    relations.append({
                        "from": obj.get("from", ""),
                        "to": obj.get("to", ""),
                        "relationType": obj.get("relationType", ""),
                    })
    return entities, relations


def _save(entities, relations):
    path = _memory_path()
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(tmp, "w") as f:
        for e in entities.values():
            f.write(json.dumps({"type": "entity", **e}, ensure_ascii=False) + "\n")
        for r in relations:
            f.write(json.dumps({"type": "relation", **r}, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def register(mcp):
    """Attach the memory tools to a FastMCP server."""

    @mcp.tool()
    def create_entities(entities: list) -> str:
        """Create entities in the shared knowledge graph. Each needs a name,
        an entityType, and observations (list of strings). Use for people,
        projects, decisions — things a future window should remember."""
        ents, rels = _load()
        created, skipped = [], []
        for e in entities:
            name = (e.get("name") or "").strip()
            if not name or name in ents:
                skipped.append(name)
                continue
            ents[name] = {
                "name": name,
                "entityType": e.get("entityType", ""),
                "observations": [str(o) for o in e.get("observations", [])],
            }
            created.append(name)
        _save(ents, rels)
        msg = f"Created: {', '.join(created)}" if created else "Created none."
        if skipped:
            msg += f" Skipped (already exist): {', '.join(s for s in skipped if s)}"
        return msg

    @mcp.tool()
    def create_relations(relations: list) -> str:
        """Link entities: each needs from, to, and relationType (active voice,
        e.g. 'carries', 'decided', 'holds'). Both entities must exist."""