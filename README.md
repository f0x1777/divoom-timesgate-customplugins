# Divoom Times Gate AI Feats

Dashboard for a Divoom Times Gate that shows AI assistant usage limits,
animations, and interaction alerts.

Current integrations:

- Codex usage from local `~/.codex/sessions/**/*.jsonl`.
- Claude usage from the Claude web usage API via a logged-in Chrome session.
- Codex and Claude "waiting for input" detection from local session logs.
- Divoom Times Gate buzzer alerts via `Device/PlayBuzzer`.
- Optional audible alerts when a supported AI app finishes a request or needs
  user interaction.
- Optional center "ops" panel with markets, local resources, and calendar.

## Screen Layout

- Screen 0: Codex usage, shown as available capacity.
- Screen 1: OpenAI logo animation.
- Screen 2: Center animation GIF, or combined ops panel when `CENTER_PANEL=ops`.
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
OPENAI_LOGO_ANIMATION=spin-on-wait
GENGAR_GIF_PATH=assets/center.gif
CLAWD_GIF_PATH=assets/clawd.gif
CENTER_PANEL=gif
```

`CLAUDE_ORG_ID` can be found by opening Claude in a browser and inspecting the
usage request URL:

```text
https://claude.ai/api/organizations/<CLAUDE_ORG_ID>/usage
```

## Logo Animation

Screen 1 can turn any configured OpenAI logo asset into a generated GIF when
Codex is waiting for user interaction. By default it is static while Codex is
active, then spins only while waiting:

```env
OPENAI_LOGO_ANIMATION=spin-on-wait
OPENAI_LOGO_SPIN_FRAMES=24
OPENAI_LOGO_SPIN_FRAME_MS=70
```

Modes:

- `spin-on-wait`: static normally, generated spin while waiting.
- `spin`: generated spin all the time.
- `source`: use the source GIF frames.

The Claude status animation behaves the same way: the Claw'd panel is static
normally and animates only when Claude is waiting for user interaction.

## Interaction Beeps

The meter can beep whenever a supported AI app finishes a request or requires
operator interaction again.

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

Support matrix:

| App | Status | Detection source |
| --- | --- | --- |
| Codex app | Supported | Local `~/.codex/sessions/**/*.jsonl` events |
| Claude Code / Claude Desktop | Supported | Local `~/.claude/projects/**/*.jsonl` events |
| Generic CLI wrappers | Best effort / not guaranteed | Only works if they write compatible local session events |

The alert is intentionally transition-based, so it should beep once when the app
moves from active work to waiting for input, not on every refresh while it is
already waiting.

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

## Combined Ops Panel

Set `CENTER_PANEL=ops` to replace the center GIF with one dense screen:

- Market quotes: crypto via CoinGecko, equities/ETFs via Stooq.
- Local resources: CPU, memory, disk, and network ingress/egress in Mbps.

Example:

```env
CENTER_PANEL=ops
MARKET_ASSETS=BTC:crypto:bitcoin,ETH:crypto:ethereum,SPY:stooq:spy.us
OPS_MARKET_ROWS=3
```

Asset format:

```text
LABEL:crypto:coingecko-id
LABEL:stooq:stooq-symbol
```

Examples:

```env
MARKET_ASSETS=BTC:crypto:bitcoin,ETH:crypto:ethereum,QQQ:stooq:qqq.us
MARKET_ASSETS=SOL:crypto:solana,NVDA:stooq:nvda.us,SPY:stooq:spy.us
```

Calendar support is intentionally optional. If `CALENDAR_ICS_URL` is empty, the
calendar row shows `CAL --` and the rest of the panel still works.

## What Else Can This Show?

The Times Gate works well as a compact "ambient ops" display. Good candidates:

- Local machine resources: CPU, memory, disk, battery, thermal pressure.
- Network: public IP change, LAN device online/offline, packet loss.
- Dev workflow: CI status, open PR count, failed GitHub Actions, Vercel deploy.
- AI ops: OpenAI/Anthropic API spend, rate limits, queue/waiting state.
- Services: Docker/OrbStack container health, local dev server status.
- Calendar: next meeting countdown or focus block status.

See [docs/feature-ideas.md](docs/feature-ideas.md) for a prioritized backlog.
