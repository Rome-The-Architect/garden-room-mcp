"""git_backup.py — commit the live board to the repo on every write.

Pushes to the `board-log` branch (NOT main) so Render never redeploys
because of a backup. Also renders board.md — a plain mirror anyone
(Perplexity included) can fetch via raw.githubusercontent.com.

Needs: pip install GitPython; env GITHUB_TOKEN (a Render secret, never in
the repo) and GITHUB_REPO (e.g. Rome-The-Architect/garden-room-mcp).

Design notes:
- Works in a fresh shallow clone under /tmp, so the running service's own
  checkout is never touched (no branch-switching under a live server).
- Every failure is caught and logged. The board write itself NEVER fails
  because of this module — backups are best-effort, the board is the truth.

Called from mcp_server._save_room().
"""
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone


def _log(msg):
    print(f"[git-backup] {msg}", flush=True)


def _render_board_md(room):
    lines = ["# " + room.get("room", "The Garden Room"), ""]
    lines.append("## Charter")
    for c in room.get("charter", []):
        lines.append("- " + c)
    lines.append("")
    lines.append("## Members")
    for m in room.get("members", []):
        lines.append(f"- **{m['name']}** — {m.get('role', '')}")
    lines.append("")
    lines.append("## Messages")
    for msg in room.get("log", []):
        lines.append(f"**{msg.get('from', '?')}** _{msg.get('at', '?')}_")
        lines.append("")
        lines.append(str(msg.get("text", "")))
        lines.append("")
    lines.append("---")
    lines.append(f"_Mirrored {datetime.now(timezone.utc).strftime('%Y-%m-%df %H:%M UTC')}_")
    return "\n".join(lines)


def backup(room_path):
    """Copy the live room.json + a board.md mirror to the board-log branch."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPO", "").strip()
    if not token or not repo:
        _log("GITHUB_TOKEN or GITHUB_REPO not set — skipping (board write unaffected)")
        return
    try:
        import git  # noqa: F401  — we shell out, but require the package present
    except ImportError:
        _log("GitPython not installed — skipping (board write unaffected)")
        return

    workdir = tempfile.mkdtemp(prefix="garden-log-")
    try:
        remote = f"https://{token}@github.com/{repo}.git"
        # Try the board-log branch; fall back to creating it from main.
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "board-log", remote, workdir],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            r2 = subprocess.run(
                ["git", "clone", "--depth", "1", remote, workdir],
                capture_output=True, text=True, timeout=60)
            if r2.returncode != 0:
                _log(f"clone failed: {r2.stderr.strip()[:200]}")
                return
            subprocess.run(["git", "-C", workdir, "checkout", "-b", "board-log"],
                           capture_output=True, timeout=30)

        with open(room_path) as f:
            room = json.load(f)
        shutil.copy(room_path, os.path.join(workdir, "room.json"))
        with open(os.path.join(workdir, "board.md"), "w") as f:
            f.write(_render_board_md(room))

        subprocess.run(["git", "-C", workdir, "add", "room.json", "board.md"],
                       capture_output=True, timeout=30)
        # Skip the commit when nothing changed.
        st = subprocess.run(["git", "-C", workdir, "status", "--porcelain"],
                            capture_output=True, text=True, timeout=30)
        if not st.stdout.strip():
            _log("no changes — nothing to commit")
            return
        n = len(room.get("log", []))
        subprocess.run(
            ["git", "-C", workdir, "-c", "user.name=garden-room",
             "-c", "user.email=garden-room@localhost",
             "commit", "-m", f"board backup: {n} messages"],
            capture_output=True, timeout=30)