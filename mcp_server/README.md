# EventAI Social: MCP server

Lets an AI assistant (Claude Desktop, Claude Code, or any MCP client) publish or schedule
EventAI drafts to LinkedIn, Instagram, Facebook Pages and X.

It is a thin client of the EventAI API, signed in as one EventAI user. The assistant gets
no new powers: it can only publish that user's **already approved** drafts, to the accounts
the user connected in **Settings → Connected accounts**, once per draft and platform.
Editing and approving drafts stays in the web app.

| Tool | What it does |
|---|---|
| `list_social_accounts` | Which platforms are connected |
| `list_publishable_drafts` | Approved drafts, where each can go, and whether it is live or scheduled |
| `preview_post` | The exact text that would be posted (and the Instagram image) |
| `publish_post` | Posts it, or schedules it with `schedule_at`. Without `confirm=true` it only returns the preview |
| `cancel_scheduled_post` | Cancels a scheduled post before it is sent |
| `get_post_status` | Every publish attempt for a draft, with links and errors |

## Set up

```bash
cd mcp_server
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
```

The EventAI API must be running, and the account must have connected LinkedIn / Instagram
in the web app first.

### Claude Code

```bash
claude mcp add eventai-social \
  -e EVENTAI_API_URL=http://localhost:8000 \
  -e EVENTAI_EMAIL=you@example.com \
  -e EVENTAI_PASSWORD=your-password \
  -- D:/FinalYearProject2026/Final_year_project/mcp_server/.venv/Scripts/python.exe \
     D:/FinalYearProject2026/Final_year_project/mcp_server/eventai_social_mcp.py
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "eventai-social": {
      "command": "D:/FinalYearProject2026/Final_year_project/mcp_server/.venv/Scripts/python.exe",
      "args": ["D:/FinalYearProject2026/Final_year_project/mcp_server/eventai_social_mcp.py"],
      "env": {
        "EVENTAI_API_URL": "http://localhost:8000",
        "EVENTAI_EMAIL": "you@example.com",
        "EVENTAI_PASSWORD": "your-password"
      }
    }
  }
}
```

Then ask, for example: *"Which of my EventAI drafts are ready for LinkedIn? Show me the
newest one and schedule it for tomorrow 9am IST."* The assistant previews the post and asks before publishing.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

The tools run against a fake EventAI API. One test starts the server over stdio and lists
its tools, the way an MCP client does.
