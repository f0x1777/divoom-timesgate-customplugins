# Divoom Times Gate AI Feats

Ambient dashboard for a Divoom Times Gate. It shows AI assistant usage limits,
market/resource telemetry, calendar context, visual waiting states, and optional
Divoom buzzer alerts.

The project is designed to be open-source friendly: personal config, cookies,
tokens, logs, and local GIF assets live in ignored files such as `.env`,
`logs/`, and `local/`.

## Platform Support

This project currently supports **macOS only**. Ubuntu/Linux and Windows
portability are planned, but the current service installer, resource monitor,
local beep fallback, and some browser-session helpers still rely on macOS
commands and paths.

## Features

- Codex usage from local `~/.codex/sessions/**/*.jsonl`.
- Claude usage from the Claude web usage API via local browser session data.
- Codex and Claude waiting-for-input detection from local session logs.
- Divoom Times Gate screen rendering through local HTTP commands.
- Skips unchanged panel uploads to avoid refresh/loading flicker.
- Divoom buzzer alerts through `Device/PlayBuzzer`.
- Limit exhaustion/reset alerts for Codex and Claude quotas.
- Configurable panel layout across the Times Gate screens.
- Market quotes for crypto, Stooq assets, and Argentina USD crypto quotes.
- Resource monitor with CPU, memory, CPU temperature, and network in/out.
- Calendar panel from one or more ICS feeds.
- Service health panel for localhost apps, APIs, TCP ports, commands, and
  Tailscale status.

## Screen Model

The Times Gate has five useful screen slots in this app:

| Screen | Default | Purpose |
| --- | --- | --- |
| `0` | Codex usage | Codex 5h, weekly, and context availability |
| `1` | `openai` | Configurable static/ambient panel |
| `2` | `center` | Configurable static/ambient panel |
| `3` | `status` | Configurable static/ambient panel |
| `4` | Claude usage | Claude 5h, weekly, design, and Sonnet availability |

Static panel slots are configured with:

```env
SCREEN_1_PANEL=openai
SCREEN_2_PANEL=center
SCREEN_3_PANEL=status
```

Supported panel values:

```text
openai
ops
center
calendar
status
health
blank
```

Example layout:

```env
SCREEN_1_PANEL=ops
SCREEN_2_PANEL=center
SCREEN_3_PANEL=calendar
```

## Refresh Behavior

The app wakes up every `REFRESH_SECONDS` for usage and panel refreshes, and
every `STATE_REFRESH_SECONDS` for waiting-state and calendar-alert checks.
Rendered panels are hashed in memory, so an unchanged screen is not uploaded to
the Divoom again. This avoids the Times Gate returning to a loading state just
because the loop ran.

```env
REFRESH_SECONDS=300
STATE_REFRESH_SECONDS=15
DIVOOM_SKIP_UNCHANGED_PANELS=1
```

Set `DIVOOM_SKIP_UNCHANGED_PANELS=0` only when debugging a device that needs a
forced repaint on every cycle. The cache lives in the running process, so it is
cleared when the service restarts.

## Quick Start

```bash
git clone git@github.com:f0x1777/divoom-timesgate-customplugins.git
cd divoom-timesgate-customplugins
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your local values:

```env
DIVOOM_IP=192.168.1.123
DIVOOM_MAC=
METER_PROVIDER=both
SCREEN_1_PANEL=ops
SCREEN_2_PANEL=center
SCREEN_3_PANEL=calendar
```

Then run a one-shot update:

```bash
.venv/bin/python main.py --once --provider both --hold-secs 0
```

Run debug mode without sending anything to the Divoom:

```bash
.venv/bin/python main.py --debug --provider both
```

Ping the Times Gate:

```bash
.venv/bin/python main.py --ping
```

## Persistent Mode On macOS

Install or restart the LaunchAgent:

```bash
scripts/install-launchagent.sh
```

Logs:

```text
logs/meter.log
logs/meter.err.log
```

Manual restart:

```bash
launchctl kickstart -k gui/$(id -u)/com.divoom.timesgate.aifeats
```

Use `LAUNCHD_LABEL=your.label scripts/install-launchagent.sh` if you want a
custom LaunchAgent label.

## Configuration Files

Use `.env.example` as the public template. Keep your real `.env` local.

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

Do not commit personal GIFs, cookies, Divoom tokens, Claude organization IDs, or
private calendar URLs.

## Claude Usage Setup

Claude usage needs `CLAUDE_ORG_ID`:

```env
CLAUDE_ORG_ID=
```

Find it by opening Claude in a browser and inspecting usage API requests:

```text
https://claude.ai/api/organizations/<CLAUDE_ORG_ID>/usage
```

Fallback manual values are supported when browser/API access is unavailable:

```env
CLAUDE_SESSION_PCT=72
CLAUDE_WEEK_PCT=45
CLAUDE_DESIGN_PCT=30
CLAUDE_SONNET_PCT=47
```

Values can be `0.72`, `72`, or `72%`.

## Codex Usage Setup

Codex usage is read from local session logs:

```text
~/.codex/sessions/**/*.jsonl
~/.codex/archived_sessions/*.jsonl
```

No API key is required for this integration. The display shows available
capacity, not used capacity.

## OPS Panel

The `ops` panel combines market quotes, resource bars, and network throughput.

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

`dolarapi:cripto` uses DolarAPI's Argentina Dólar Cripto quote. The panel
renders that quote as ARS without `K` abbreviation.

Resource metrics:

- CPU usage
- Memory usage
- CPU temperature, when a supported local sensor command is available
- Network ingress in Mbps
- Network egress in Mbps

Network interfaces default to `en0,en1`. Override them with:

```env
NETWORK_INTERFACES=en0,utun0
```

Resource values are bucketed before rendering, so small sampling noise does not
trigger a Divoom panel upload. Defaults are 5 percentage points for CPU and
memory, and 0.25 Mbps for network throughput.

```env
RESOURCE_PERCENT_BUCKET=5
RESOURCE_NETWORK_BUCKET_MBPS=0.25
```

CPU temperature is optional. On Apple Silicon, `macmon` is preferred because it
can report temperatures without `sudo`:

```env
CPU_TEMP_COMMAND=macmon pipe -s 1 -i 1000
CPU_TEMP_MIN_C=35
CPU_TEMP_MAX_C=100
```

## Calendar Panel

The `calendar` panel reads upcoming events from one or more ICS feeds. Multiple
feeds are merged into one chronological list, so events from different accounts
appear together on the same screen.

```env
SCREEN_3_PANEL=calendar
CALENDAR_ICS_URL_1=https://example.com/calendar-1.ics
CALENDAR_ICS_URL_2=https://example.com/calendar-2.ics
CALENDAR_ICS_URL_3=https://example.com/calendar-3.ics
CALENDAR_MAX_EVENTS=3
CALENDAR_CACHE_SECONDS=300
CALENDAR_LOOKAHEAD_HOURS=48
CALENDAR_EVENT_ALERT_WINDOW_SECONDS=90
```

For a single calendar, `CALENDAR_ICS_URL=https://...` still works. For a compact
list, `CALENDAR_ICS_URLS=url1,url2,url3` also works. `webcal://...` subscription
links are accepted and normalized to `https://...` internally.

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

The `health` panel checks services and Tailscale.

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

The bottom `TS` row reports Tailscale status and online peer count. Disable it
with:

```env
TAILSCALE_HEALTH=0
```

## Beeps And Alerts

Interaction alerts:

- Codex: beeps when local session state transitions into `task_complete`.
- Claude: beeps when local session state transitions into assistant `end_turn`.

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

One-shot full update:

```bash
.venv/bin/python main.py --once --provider both --hold-secs 0
```

Only Codex:

```bash
.venv/bin/python main.py --once --provider codex --hold-secs 0
```

Only Claude:

```bash
.venv/bin/python main.py --once --provider claude --hold-secs 0
```

Debug:

```bash
.venv/bin/python main.py --debug --provider both
```

Fixed test display:

```bash
.venv/bin/python main.py --test-display --provider both
```

Run tests:

```bash
.venv/bin/python -m unittest discover -s tests
```

## Troubleshooting

If screens stay loading:

1. Run `main.py --ping`.
2. Check `DIVOOM_IP`.
3. Set `DIVOOM_MAC` and keep `DIVOOM_AUTO_DISCOVER=1`.
4. Check `logs/meter.err.log`.

If the Divoom beep does not sound:

1. Run the manual buzzer test above.
2. Confirm `DIVOOM_BEEP=1`.
3. Check for `[meter] Divoom beep OK (...)` in `logs/meter.log`.
4. Increase `DIVOOM_BEEP_TOTAL_MS`.

If Claude usage is unknown:

1. Confirm `CLAUDE_ORG_ID`.
2. Open Claude in your browser and make sure you are logged in.
3. Use fallback env values if browser scraping/API access is not available.

If calendar says `NO EVENTS`:

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
