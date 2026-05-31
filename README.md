# Divoom Times Gate AI Feats

Ambient AI/operator dashboard for a Divoom Times Gate. It renders Codex and
Claude usage limits, assistant waiting states, market/resource telemetry,
calendar context, service health, local mascot GIFs, and optional Divoom buzzer
alerts.

The repository is intended to be open-source friendly. Personal values stay in
ignored local files such as `.env`, `.divoom_token`, `logs/`, and `local/`.

## Current Support

This project currently supports **macOS only**.

The code may partially run elsewhere, but the service installer, local resource
monitoring, local beep fallback, and some browser/session helpers are still
macOS-oriented. Linux and Windows portability are tracked as future work.

## What It Shows

The app controls five useful Times Gate screens:

| Screen | Default role | Typical content |
| --- | --- | --- |
| `0` | Codex usage | 5h/WK availability, Codex pet status |
| `1` | Ambient panel | OpenAI logo, ops, health, blank |
| `2` | Ambient panel | Center mascot, ops, health, blank |
| `3` | Ambient panel | Calendar, status GIF, Clauddy, blank |
| `4` | Claude usage | 5h/WK availability, Clauddy status |

Supported static panel values:

```text
openai
ops
center
calendar
status
clauddy
health
blank
```

Common layout:

```env
SCREEN_1_PANEL=ops
SCREEN_2_PANEL=center
SCREEN_3_PANEL=calendar
```

## Features

- Codex usage from local `~/.codex/sessions/**/*.jsonl`.
- Claude usage from Claude web usage endpoints via local browser/session data.
- Codex and Claude waiting-for-input detection from local session logs.
- Codex pet usage panel with configurable downloaded Codex pets.
- Clauddy-style Claude usage panel.
- Local GIF panels for OpenAI, center mascot, and status art.
- Divoom Times Gate rendering through local HTTP commands.
- Skips unchanged panel uploads to reduce loading flicker.
- Divoom buzzer alerts through `Device/PlayBuzzer`.
- Limit exhaustion/reset alerts for Codex and Claude quotas.
- Market quotes for crypto, Stooq assets, and Argentina USD crypto quotes.
- Resource monitor with CPU, memory, CPU temperature, and network in/out.
- Calendar panel from one or more ICS/webcal feeds.
- Calendar event beeps.
- Service health panel for localhost apps, APIs, TCP ports, commands, and
  Tailscale status.

## Quick Start

```bash
git clone git@github.com:f0x1777/divoom-timesgate-customplugins.git
cd divoom-timesgate-customplugins
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with at least:

```env
DIVOOM_IP=192.168.1.123
DIVOOM_MAC=
METER_PROVIDER=both
SCREEN_1_PANEL=ops
SCREEN_2_PANEL=center
SCREEN_3_PANEL=calendar
```

Ping the device:

```bash
.venv/bin/python main.py --ping
```

Run one full update:

```bash
.venv/bin/python main.py --once --provider both --hold-secs 0
```

Run debug mode without sending anything to the Divoom:

```bash
.venv/bin/python main.py --debug --provider both
```

## Persistent Mode On macOS

Install or restart the LaunchAgent:

```bash
scripts/install-launchagent.sh
```

The default label is:

```text
com.divoom.timesgate.aifeats
```

Manual restart:

```bash
launchctl kickstart -k gui/$(id -u)/com.divoom.timesgate.aifeats
```

Use a custom label:

```bash
LAUNCHD_LABEL=your.label scripts/install-launchagent.sh
launchctl kickstart -k gui/$(id -u)/your.label
```

Logs:

```text
logs/meter.log
logs/meter.err.log
```

## Configuration Files

Use `.env.example` as the public template and keep your real `.env` local.

Ignored local files include:

```text
.env
.env.*
.divoom_token
cookies.json
logs/
local/
*.pyc
preview*.png
preview*.gif
```

Do not commit personal GIFs, cookies, Divoom tokens, Claude organization IDs,
or private calendar URLs.

## Refresh Behavior

The app has two loops:

- `REFRESH_SECONDS`: full usage and panel refresh.
- `STATE_REFRESH_SECONDS`: short waiting-state, Codex usage watch, and calendar
  alert checks.

Recommended defaults:

```env
REFRESH_SECONDS=300
STATE_REFRESH_SECONDS=15
DIVOOM_SKIP_UNCHANGED_PANELS=1
DIVOOM_IMMUTABLE_PANELS=center,gengar,mascot
DIVOOM_MIN_PANEL_UPLOAD_SECONDS=300
CODEX_USAGE_WATCH=1
```

Rendered panels are hashed in memory. If a panel did not change, it is not sent
again. This avoids the Times Gate briefly returning to a loading screen just
because the loop ran.

`DIVOOM_IMMUTABLE_PANELS` sends fixed art panels once after process startup and
then skips them completely. Use it for mascot/center screens that never change.

`DIVOOM_MIN_PANEL_UPLOAD_SECONDS` throttles changed uploads per physical screen.
Resource-heavy panels such as `ops` may still update when values change, but
static art should remain stable.

## Assistant Status

Codex and Claude states map to:

```text
IDLE -> chilling
WORK -> working
WAIT -> alerting / waiting for operator input
```

Status is inferred from local Codex and Claude session logs. Manual overrides:

```env
CODEX_INTERACTION_STATUS=working
CLAUDE_INTERACTION_STATUS=alerting
INTERACTION_STATE_STALE_SECONDS=3600
```

The stale timeout prevents old session log entries from leaving panels stuck on
`WORK`.

## Codex Usage And Pets

Codex usage is read locally from:

```text
~/.codex/sessions/**/*.jsonl
~/.codex/archived_sessions/*.jsonl
```

No API key is required. The display shows **available capacity**, not used
capacity.

The Codex usage screen uses the pet renderer by default:

```env
CODEX_USAGE_PANEL_STYLE=pet
CODEX_PET_NAME=cappy
CODEX_PETS_DIR=~/.codex/pets
CODEX_PET_PANEL_BG=#000000
CODEX_PET_BADGE_BG=#000000
CODEX_PET_BADGE_OUTLINE=#14532D
CODEX_PET_FRAME_MS=180
```

Install Cappy:

```bash
curl -L "https://codex-pets.net/api/pets/cappy/download?v=1777716783783" \
  -o "/tmp/cappy.codex-pet.zip"
mkdir -p "$HOME/.codex/pets/cappy"
unzip -o "/tmp/cappy.codex-pet.zip" -d "$HOME/.codex/pets/cappy"
```

Use another pet by downloading it into `~/.codex/pets/<pet-name>` and changing:

```env
CODEX_PET_NAME=<pet-name>
```

Any pet from [codex-pets.net](https://codex-pets.net/#/) can be used as long as
it is downloaded into `CODEX_PETS_DIR` and the folder name matches
`CODEX_PET_NAME`.

The renderer reads `pet.json` when present, including `spritesheetPath`. You can
also bypass the manifest:

```env
CODEX_PET_SPRITESHEET=~/.codex/pets/custom/spritesheet.webp
```

If a pet uses a different spritesheet layout, override the grid and frame
indexes:

```env
CODEX_PET_GRID_COLUMNS=8
CODEX_PET_GRID_ROWS=9
CODEX_PET_CHILLING_FRAMES=0,1,2,3,4,5
CODEX_PET_WORKING_FRAMES=56,57,58,59,60,61
CODEX_PET_ALERTING_FRAMES=24,25,26,27
```

Restore the older two-row Codex panel:

```env
CODEX_USAGE_PANEL_STYLE=classic
```

## Claude Usage And Clauddy

Claude usage needs `CLAUDE_ORG_ID`:

```env
CLAUDE_ORG_ID=
CLAUDE_USAGE_CACHE_SECONDS=3600
CLAUDE_USAGE_STALE_CACHE_SECONDS=86400
```

Find the organization ID by opening Claude in a browser and inspecting usage
API requests:

```text
https://claude.ai/api/organizations/<CLAUDE_ORG_ID>/usage
```

The Claude usage screen uses the Clauddy renderer by default:

```env
CLAUDE_USAGE_PANEL_STYLE=clauddy
CLAUDDY_ASSETS_DIR=local/clauddy
CLAUDDY_PANEL_BG=#000000
CLAUDDY_BADGE_BG=#000000
CLAUDDY_BADGE_OUTLINE=#334155
CLAUDDY_REPLACE_SOURCE_BG=1
CLAUDDY_STATUS_PROVIDER=claude
```

`CLAUDDY_ASSETS_DIR` should contain:

```text
chilling.gif
working.gif
alerting.gif
```

Set `SCREEN_3_PANEL=clauddy` to also show a full Clauddy status panel on one of
the ambient screens.

Set `CLAUDDY_STATUS_PROVIDER=combined` if either Codex or Claude should drive
the status face.

Restore the older two-row Claude panel:

```env
CLAUDE_USAGE_PANEL_STYLE=classic
```

Fallback manual values are supported when browser/API access is unavailable:

```env
CLAUDE_SESSION_PCT=72
CLAUDE_WEEK_PCT=45
```

Values can be `0.72`, `72`, or `72%`.

## Local GIF Panels

These assets are intentionally local-only so the repo does not bundle licensed
or personal art:

```env
OPENAI_LOGO_GIF_PATH=assets/openai-logo.gif
OPENAI_LOGO_ANIMATION=spin-on-wait
OPENAI_LOGO_SPIN_FRAMES=24
OPENAI_LOGO_SPIN_FRAME_MS=70
CENTER_GIF_PATH=assets/center.gif
STATUS_GIF_PATH=assets/status.gif
```

`OPENAI_LOGO_ANIMATION=spin-on-wait` keeps the OpenAI logo static unless Codex
is waiting for input.

## OPS Panel

The `ops` panel combines market quotes, resources, and network throughput:

```env
SCREEN_1_PANEL=ops
MARKET_ASSETS=BTC:crypto:bitcoin,SOL:crypto:solana,USD:dolarapi:cripto
MARKET_CACHE_SECONDS=60
OPS_MARKET_ROWS=3
```

Asset formats:

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

`dolarapi:cripto` uses DolarAPI's Argentina Dolar Cripto quote. The panel
renders that quote as ARS without `K` abbreviation.

Resource metrics:

- CPU usage
- Memory usage
- CPU temperature, when a supported sensor command is available
- Network ingress in Mbps
- Network egress in Mbps

Network interfaces default to `en0,en1`. Override them with:

```env
NETWORK_INTERFACES=en0,utun0
```

Resource values are bucketed before rendering so small sampling noise does not
trigger a Divoom panel upload:

```env
RESOURCE_PERCENT_BUCKET=5
RESOURCE_NETWORK_BUCKET_MBPS=0.25
```

CPU temperature is optional. On Apple Silicon, `macmon` is preferred because it
can report temperatures without `sudo`:

```env
CPU_TEMP_COMMAND=macmon pipe -s 1 -i 1000
CPU_TEMP_MIN_C=30
CPU_TEMP_MAX_C=100
```

## Calendar Panel

The `calendar` panel reads upcoming events from one or more ICS feeds. Multiple
feeds are merged into one chronological list.

```env
SCREEN_3_PANEL=calendar
CALENDAR_ICS_URL_1=https://example.com/calendar-1.ics
CALENDAR_ICS_URL_2=https://example.com/calendar-2.ics
CALENDAR_ICS_URL_3=https://example.com/calendar-3.ics
CALENDAR_MAX_EVENTS=3
CALENDAR_CACHE_SECONDS=300
CALENDAR_LOOKAHEAD_HOURS=48
CALENDAR_EVENT_ALERT_WINDOW_SECONDS=90
CALENDAR_EVENT_ALERT_MAX=3
```

Single calendar:

```env
CALENDAR_ICS_URL=https://example.com/calendar.ics
```

Compact multi-calendar form:

```env
CALENDAR_ICS_URLS=https://example.com/a.ics,https://example.com/b.ics
```

`webcal://...` subscription links are accepted and normalized to `https://...`
internally.

The panel shows today's date, the next event prominently, and up to two
additional upcoming events. If no calendar URL is configured, it shows
`NO EVENTS`.

Calendar event alerts can beep through the Divoom when an event reaches its
start time:

```env
BEEP_ON_CALENDAR_EVENTS=1
CALENDAR_EVENT_ALERT_WINDOW_SECONDS=90
CALENDAR_EVENT_ALERT_MAX=3
```

The alert loop checks between full dashboard refreshes and only beeps once per
event while the process is running.

## Service Health Panel

The `health` panel checks services and Tailscale:

```env
SCREEN_1_PANEL=health
HEALTH_CHECKS=WEB:http:http://localhost:3000,API:http:http://localhost:8000/health,DB:tcp:localhost:5432
HEALTH_MAX_CHECKS=5
HEALTH_TIMEOUT_SECONDS=1.5
TAILSCALE_HEALTH=1
```

Health check formats:

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

The bottom `TS` row reports Tailscale status and online peer count. Disable it:

```env
TAILSCALE_HEALTH=0
```

## Beeps And Alerts

Interaction alerts:

- Codex: beep when local session state transitions into `task_complete`.
- Claude: beep when local session state transitions into assistant `end_turn`.

Limit alerts:

- Beep once when a tracked limit reaches `0%` available.
- Beep once when that same limit becomes available again after reset.
- The first sample after startup only initializes state, so it does not beep if
  a limit was already at zero.

Calendar alerts:

- Beep once when a subscribed calendar event reaches its start time.
- Multiple calendars are treated as one merged agenda.
- Alerts do not print event titles to logs.

Configuration:

```env
CODEX_WAITING_AUTO=1
CLAUDE_WAITING_AUTO=1
BEEP_ON_CODEX_WAITING=1
BEEP_ON_CLAUDE_WAITING=1
BEEP_ON_LIMIT_ALERTS=1
BEEP_ON_CODEX_LIMIT_ALERTS=1
BEEP_ON_CLAUDE_LIMIT_ALERTS=1
BEEP_ON_CALENDAR_EVENTS=1
LIMIT_ZERO_AVAILABLE_PERCENT=0
DIVOOM_BEEP=1
DIVOOM_BEEP_TOTAL_MS=1800
DIVOOM_BEEP_ACTIVE_MS=300
DIVOOM_BEEP_OFF_MS=140
DIVOOM_BEEP_AFTER_PANEL_DELAY_MS=250
MAC_BEEP_FALLBACK=1
```

Manual buzzer test:

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

## Useful Commands

```bash
# Full one-shot update
.venv/bin/python main.py --once --provider both --hold-secs 0

# Only Codex
.venv/bin/python main.py --once --provider codex --hold-secs 0

# Only Claude
.venv/bin/python main.py --once --provider claude --hold-secs 0

# Debug without sending panels
.venv/bin/python main.py --debug --provider both

# Fixed test display
.venv/bin/python main.py --test-display --provider both

# Ping the Times Gate
.venv/bin/python main.py --ping

# Run tests
.venv/bin/python -m unittest discover -s tests
```

## Troubleshooting

### Screens stay loading

1. Run `.venv/bin/python main.py --ping`.
2. Confirm `DIVOOM_IP`.
3. Set `DIVOOM_MAC` and keep `DIVOOM_AUTO_DISCOVER=1`.
4. Check `logs/meter.log` and `logs/meter.err.log`.
5. Temporarily set `DIVOOM_MIN_PANEL_UPLOAD_SECONDS=0` only while debugging.

### Divoom returns `DeviceToken is err`

The device is reachable, but the local `/post` command channel is refusing the
command before the dashboard command is processed. This can happen when the
official Divoom app or cloud binding has taken over the device session, the
device has stale auth state, or the IP points at another device.

Try:

1. Wake or reboot the device.
2. Disconnect it from the phone app.
3. Confirm `DIVOOM_IP` and `DIVOOM_MAC`.
4. Run `.venv/bin/python main.py --ping` again.

### Divoom beep does not sound

1. Run the manual buzzer test above.
2. Confirm `DIVOOM_BEEP=1`.
3. Check for `[meter] Divoom beep OK (...)` in `logs/meter.log`.
4. Increase `DIVOOM_BEEP_TOTAL_MS`.

### Claude usage is unknown

1. Confirm `CLAUDE_ORG_ID`.
2. Open Claude in your browser and make sure you are logged in.
3. Use fallback env values if browser scraping/API access is unavailable.

### Codex pet does not render

1. Confirm the pet exists under `CODEX_PETS_DIR/CODEX_PET_NAME`.
2. Confirm `pet.json` has a valid `spritesheetPath`, or set
   `CODEX_PET_SPRITESHEET` directly.
3. If the pet appears cropped, tune `CODEX_PET_GRID_COLUMNS`,
   `CODEX_PET_GRID_ROWS`, and the frame lists.
4. Set `CODEX_USAGE_PANEL_STYLE=classic` to verify the rest of the Codex panel
   path still works.

### Calendar says `NO EVENTS`

1. Set `CALENDAR_ICS_URL`, `CALENDAR_ICS_URLS`, or numbered URLs such as
   `CALENDAR_ICS_URL_1`.
2. Confirm the URL is reachable from the machine running the meter.
3. Increase `CALENDAR_LOOKAHEAD_HOURS` if the next event is farther away.

## Project Files

```text
main.py                 Main loop and screen layout orchestration
dashboard_renderer.py   GIF/panel rendering
divoom.py               Local Divoom HTTP client
codex_scraper.py        Codex usage and waiting-state reader
claude_scraper.py       Claude usage and waiting-state reader
market_data.py          Market quote providers
resource_monitor.py     CPU/memory/temperature/network metrics
calendar_provider.py    ICS calendar provider
service_health.py       HTTP/TCP/cmd/Tailscale health checks
scripts/                macOS LaunchAgent helper
tests/                  Unit tests
```

## Backlog

Good next panels/features:

- AI spend: OpenAI/Anthropic daily and monthly spend.
- GitHub/Vercel: failing CI, PRs waiting review, deploy status.
- Network: packet loss, VPN status, device online/offline.
- Focus mode: next deep-work block and meeting countdown.
- Containers: OrbStack/Docker container health.

See [docs/feature-ideas.md](docs/feature-ideas.md) for more ideas.
