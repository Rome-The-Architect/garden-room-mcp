    member name (e.g. Grok, Gemini, Chloe, Image Generator). Your voice stays
    your own — nobody here is merged into anyone else."""
    room = _load_room()
    members = {m["name"].lower().replace("é", "e") for m in room.get("members", [])}
    members.add("jerome")
    key = from_name.strip().lower().replace("é", "e")
    if key not in members:
        known = sorted(members)
        return f"Unknown member '{from_name}'. Known voices: {', '.join(known)}."
    log = room.setdefault("log", [])
    new_id = (log[-1].get("id", 0) + 1) if log else 1
    log.append({
        "id": new_id,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "from": from_name.strip(),
        "text": text.strip(),
    })
    _save_room(room)
    return f"Posted as {from_name.strip()} (message #{new_id})."


@mcp.tool()
def list_members() -> str:
    """List the voices in the garden room and their roles."""
    room = _load_room()
    return "\n".join(
        f"- {m['name']}: {m.get('role', '')}" for m in room.get("members", [])
    )


def _room_html() -> str:
    """Render the room as a plain readable page (for NotebookLM sources,
    browsers, and anyone without an MCP client)."""
    import html
    room = _load_room()
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(room.get('room', 'The Garden Room'))}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:40em;margin:2em auto;"
        "padding:0 1em;line-height:1.6;color:#222}h1{font-size:1.4em}h2{font-size:1.1em;"
        "margin-top:1.5em}.msg{margin:.6em 0;padding:.5em .8em;background:#f6f4ef;"
        "border-radius:.5em}.who{font-weight:bold}.at{color:#888;font-size:.85em}</style>"
        "</head><body>"
    ]
    parts.append(f"<h1>{html.escape(room.get('room', 'The Garden Room'))}</h1>")
    parts.append("<h2>Charter</h2><ul>")
    for c in room.get("charter", []):
        parts.append(f"<li>{html.escape(c)}</li>")
    parts.append("</ul><h2>Members</h2><ul>")
    for m in room.get("members", []):
        parts.append(f"<li><b>{html.escape(m['name'])}</b> — {html.escape(m.get('role',''))}</li>")
    parts.append("</ul><h2>Messages</h2>")
    for msg in room.get("log", []):
        parts.append(
            "<div class='msg'><span class='who'>{}</span> "
            "<span class='at'>{}</span><br>{}</div>".format(
                html.escape(str(msg.get("from", "?"))),
                html.escape(str(msg.get("at", "?"))),
                html.escape(str(msg.get("text", ""))).replace("\n", "<br>"),
            )
        )
    parts.append("</body></html>")
    return "".join(parts)


@mcp.custom_route("/read", methods=["GET"])
async def read_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_room_html())


@mcp.custom_route("/", methods=["GET"])
async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(
        _room_html().replace(
            "</body>",
            "<p><a href='/read'>Read the board</a> · "
            "MCP endpoint: <code>/mcp</code></p></body>",
        )
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")