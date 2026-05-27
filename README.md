# Divoom Times Gate AI Feats

Dashboard for a Divoom Times Gate that shows AI assistant usage limits,
animations, and interaction alerts.

Current integrations:

- Codex usage from local `~/.codex/sessions/**/*.jsonl`.
- Claude usage from the Claude web usage API via a logged-in Chrome session.
- Codex and Claude "waiting for input" detection from local session logs.
- Divoom Times Gate buzzer alerts via `Device/PlayBuzzer`.

## Screen Layout

- Screen 0: Codex usage, shown as available capacity.
- Screen 1: OpenAI logo animation.
- Screen 2: Center animation GIF.
- Screen 3: Claude status animation.
- Screen 4: Claude usage, shown as available capacity.

GIF assets are local-only. Set their paths in `.env`; do not commit personal or
licensed assets unless you have the right to redistribute them.

## Local Configuration

Personal configuration lives in `.env`, which is ignored by git. To set up a
new machine:

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then edit `.env`:

```env
DIVOOM_IP=192.168.1.123
DIVOOM_MAC=
CLAUDE_ORG_ID=
OPENAI_LOGO_GIF_PATH=assets/openai-logo.gif
GENGAR_GIF_PATH=assets/center.gif
CLAWD_GIF_PATH=assets/clawd.gif
```

`CLAUDE_ORG_ID` can be found by opening Claude in a browser and inspecting the
usage request URL:

```text
https://claude.ai/api/organizations/<CLAUDE_ORG_ID>/usage
```

## Interaction Beeps

The meter beeps whenever Codex or Claude finishes a turn and is waiting for the
operator again.

This is implemented as a state transition:

- Codex: latest local Codex session event changes from `task_started` to
  `task_complete`.
- Claude: latest local Claude session event changes to an assistant
  `end_turn`.

The loop checks this lightweight state every `STATE_REFRESH_SECONDS` seconds
between full usage refreshes. When the state changes from active to waiting,
the meter:

1. Animates the relevant panel.
2. Calls the Divoom Times Gate buzzer.
3. Falls back to a macOS beep only if the Divoom buzzer fails.

Relevant env flags:

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

The Divoom command used is:

```json
{
  "Command": "Device/PlayBuzzer",
  "ActiveTimeInCycle": 200,
  "OffTimeInCycle": 150,
  "PlayTotalTime": 1200
}
```

## Manual Buzzer Test

Run this from the repo root after setting `DIVOOM_IP` in `.env`:

```bash
.venv/bin/python - <<'PY'
import os
from dotenv import load_dotenv
import divoom

load_dotenv()
ok = divoom.play_buzzer(
    os.environ["DIVOOM_IP"],
    play_total_time=1200,
    active_time_in_cycle=200,
    off_time_in_cycle=150,
)
print(f"Divoom buzzer test: {ok}")
PY
```

Expected output:

```text
Divoom buzzer test: True
```

## Run The Meter

One-shot send:

```bash
.venv/bin/python main.py --once --provider both --hold-secs 0
```

Debug usage without sending anything to the device:

```bash
.venv/bin/python main.py --debug --provider both
```

## macOS LaunchAgent

Install or restart the persistent meter:

```bash
scripts/install-launchagent.sh
```

Logs:

```text
logs/meter.log
logs/meter.err.log
```

## What Else Can This Show?

The Times Gate works well as a compact "ambient ops" display. Good candidates:

- Local machine resources: CPU, memory, disk, battery, thermal pressure.
- Network: public IP change, LAN device online/offline, packet loss.
- Dev workflow: CI status, open PR count, failed GitHub Actions, Vercel deploy.
- AI ops: OpenAI/Anthropic API spend, rate limits, queue/waiting state.
- Services: Docker/OrbStack container health, local dev server status.
- Calendar: next meeting countdown or focus block status.

See [docs/feature-ideas.md](docs/feature-ideas.md) for a prioritized backlog.
