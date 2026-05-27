# Interaction Alerts

The project supports audible and visual alerts when a supported AI app finishes
work or needs user interaction.

## Supported Apps

| App | Status | Detection source |
| --- | --- | --- |
| Codex app | Supported | Local `~/.codex/sessions/**/*.jsonl` events |
| Claude Code / Claude Desktop | Supported | Local `~/.claude/projects/**/*.jsonl` events |
| Generic CLI wrappers | Best effort / not guaranteed | Only works if they write compatible local session events |

## Behavior

The meter watches for state transitions:

- Codex: `task_started` -> `task_complete`
- Claude: assistant `tool_use` or user/tool-result activity -> assistant
  `end_turn`

When a transition into waiting state is detected, the meter:

1. Re-renders the relevant panel with the waiting animation.
2. Calls `Device/PlayBuzzer` on the Divoom Times Gate.
3. Falls back to a macOS beep if `MAC_BEEP_FALLBACK=1` and the Divoom buzzer
   call fails.

It should beep once per transition into waiting state. It should not beep on
every refresh while the app remains idle.

## Configuration

```env
CODEX_WAITING_AUTO=1
CLAUDE_WAITING_AUTO=1
BEEP_ON_CODEX_WAITING=1
BEEP_ON_CLAUDE_WAITING=1
DIVOOM_BEEP=1
DIVOOM_BEEP_TOTAL_MS=1200
DIVOOM_BEEP_ACTIVE_MS=200
DIVOOM_BEEP_OFF_MS=150
MAC_BEEP_FALLBACK=1
STATE_REFRESH_SECONDS=15
```

Disable one provider's audible alert while keeping visual animation:

```env
BEEP_ON_CODEX_WAITING=0
BEEP_ON_CLAUDE_WAITING=1
```

Disable Divoom audio but keep macOS fallback:

```env
DIVOOM_BEEP=0
MAC_BEEP_FALLBACK=1
```

## Manual Buzzer Test

```bash
.venv/bin/python - <<'PY'
import os
from dotenv import load_dotenv
import divoom

load_dotenv()
print(divoom.play_buzzer(os.environ["DIVOOM_IP"]))
PY
```
