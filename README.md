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
- Optional center panels for ops telemetry and service health.

## Screen Layout

- Screen 0: Codex usage, shown as available capacity.
- Screen 1: Configurable static panel, default OpenAI logo animation.
- Screen 2: Configurable static panel, default center GIF.
- Screen 3: Configurable static panel, default Claude status animation.
- Screen 4: Claude usage, shown as available capacity.

Static panel slots use these values:

```env
SCREEN_1_PANEL=openai
SCREEN_2_PANEL=gengar
SCREEN_3_PANEL=clawd
```

Supported panel values: `openai`, `ops`, `gengar`, `calendar`, `clawd`,
`health`, `blank`.

Example personal layout:

```env
SCREEN_1_PANEL=ops
SCREEN_2_PANEL=gengar
SCREEN_3_PANEL=calendar
```

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
2. Waits briefly so the panel refresh does not interrupt the sound.
3. Calls the Divoom Times Gate buzzer.
4. Falls back to a macOS beep only if the Divoom buzzer fails.

Support matrix:

| App | Status | Detection source |
| --- | --- | --- |
| Codex app | Supported | Local `~/.codex/sessions/**/*.jsonl` events |
| Claude Code / Claude Desktop | Supported | Local `~/.claude/projects/**/*.jsonl` events |
| Generic CLI wrappers | Best effort / not guaranteed | Only works if they write compatible local session events |

The alert is intentionally transition-based, so it should beep once when the app
moves from active work to waiting for input, not on every refresh while it is
already waiting.

Limit exhaustion alerts are also transition-based. The meter beeps once when a
tracked limit reaches `0%` available, and once when that same limit becomes
available again after a reset. The first sample after startup only initializes
state, so restarting the service will not beep just because a limit was already
at zero.

Relevant env flags:

```env
CODEX_WAITING_AUTO=1
CLAUDE_WAITING_AUTO=1
BEEP_ON_CODEX_WAITING=1
BEEP_ON_CLAUDE_WAITING=1
BEEP_ON_LIMIT_ALERTS=1
BEEP_ON_CODEX_LIMIT_ALERTS=1
BEEP_ON_CLAUDE_LIMIT_ALERTS=1
LIMIT_ZERO_AVAILABLE_PERCENT=0
DIVOOM_BEEP=1
DIVOOM_BEEP_TOTAL_MS=1800
DIVOOM_BEEP_ACTIVE_MS=300
DIVOOM_BEEP_OFF_MS=140
DIVOOM_BEEP_AFTER_PANEL_DELAY_MS=250
MAC_BEEP_FALLBACK=1
STATE_REFRESH_SECONDS=15
```

The Divoom command used is:

```json
{
  "Command": "Device/PlayBuzzer",
  "ActiveTimeInCycle": 300,
  "OffTimeInCycle": 140,
  "PlayTotalTime": 1800
}
```

## Manual Buzzer Test

Run this from the repo root after setting `DIVOOM_IP` in `.env`:

```bash
.venv/bin/python - <<'PY'
import os
from dotenv import load_dotenv
import divoom

load_dotenv(".env")
ok = divoom.play_buzzer(
    os.environ["DIVOOM_IP"],
    play_total_time=1800,
    active_time_in_cycle=300,
    off_time_in_cycle=140,
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

Set `SCREEN_1_PANEL=ops`, `SCREEN_2_PANEL=ops`, or `CENTER_PANEL=ops` to show
one dense screen:

- Market quotes: crypto via CoinGecko, equities/ETFs via Stooq.
- Local resources: CPU, memory, disk, and network ingress/egress in Mbps.

Example:

```env
SCREEN_1_PANEL=ops
MARKET_ASSETS=BTC:crypto:bitcoin,SOL:crypto:solana,USD:dolarapi:cripto
OPS_MARKET_ROWS=3
```

Asset format:

```text
LABEL:crypto:coingecko-id
LABEL:stooq:stooq-symbol
LABEL:dolarapi:dolarapi-casa
```

Examples:

```env
MARKET_ASSETS=BTC:crypto:bitcoin,ETH:crypto:ethereum,QQQ:stooq:qqq.us
MARKET_ASSETS=SOL:crypto:solana,NVDA:stooq:nvda.us,SPY:stooq:spy.us
MARKET_ASSETS=BTC:crypto:bitcoin,SOL:crypto:solana,USD:dolarapi:cripto
```

For Argentina dollar quotes, `dolarapi:cripto` uses DolarAPI's Dólar Cripto
endpoint, a crypto-market USD quote.

The compact ops panel uses the lower area for network ingress/egress by default.

## Calendar Panel

Set any static slot to `calendar` to show the next events from an ICS feed:

```env
SCREEN_3_PANEL=calendar
CALENDAR_ICS_URL=https://example.com/private-calendar.ics
CALENDAR_MAX_EVENTS=3
CALENDAR_CACHE_SECONDS=300
CALENDAR_LOOKAHEAD_HOURS=48
```

The panel shows today's date, the next event prominently, and up to two
additional upcoming events.

## Service Health Panel

Set `CENTER_PANEL=health` to replace the center GIF with service checks and
Tailscale status:

```env
CENTER_PANEL=health
HEALTH_CHECKS=WEB:http:http://localhost:3000,API:http:http://localhost:8000/health,DB:tcp:localhost:5432
HEALTH_MAX_CHECKS=5
HEALTH_TIMEOUT_SECONDS=1.5
TAILSCALE_HEALTH=1
```

Health check format:

```text
LABEL:http:URL
LABEL:tcp:host:port
LABEL:cmd:/path/to/command --flag
```

Examples:

```env
HEALTH_CHECKS=WEB:http:http://localhost:3000,API:http:http://localhost:8787/health,PG:tcp:localhost:5432
HEALTH_CHECKS=VITE:http:http://localhost:5173,REDIS:tcp:localhost:6379,DOCKER:cmd:docker ps
```

The panel shows an aggregate `SVC ok/total`, up to five rows with `OK` or
`FAIL`, and a bottom `TS` row for Tailscale/VPN state.

## What Else Can This Show?

The Times Gate works well as a compact "ambient ops" display. Good candidates:

- Local machine resources: CPU, memory, disk, battery, thermal pressure.
- Network: public IP change, LAN device online/offline, packet loss.
- Dev workflow: CI status, open PR count, failed GitHub Actions, Vercel deploy.
- AI ops: OpenAI/Anthropic API spend, rate limits, queue/waiting state.
- Services: Docker/OrbStack container health, local dev server status.
- Calendar: next meeting countdown or focus block status.

See [docs/feature-ideas.md](docs/feature-ideas.md) for a prioritized backlog.
