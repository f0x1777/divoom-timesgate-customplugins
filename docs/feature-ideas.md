# Feature Ideas

Prioritized ideas for turning the Times Gate into a small ambient operations
panel.

## Near Term

1. Local resources panel

   Initial support exists in the combined `CENTER_PANEL=ops` screen: CPU,
   memory, CPU temperature, and network ingress/egress. Thermal pressure and
   battery are still good optional additions.

2. Service health panel

   Track a short list of local URLs and ports, for example `localhost:3000`,
   `localhost:8000`, a local API, or the Divoom asset server.

3. AI spend panel

   Show OpenAI and Anthropic daily/monthly spend, plus projected end-of-month
   spend. This should be off by default because it may require API keys.

4. GitHub work panel

   Show failing CI, open PRs waiting for review, or the latest deploy status.
   Keep tokens in `.env` or an OS keychain, never in the repo.

5. Pomodoro / focus timer

   Add an optional local Pomodoro panel with configurable work/break lengths,
   Divoom buzzer alerts when a block ends, and a simple state file so the timer
   survives dashboard refreshes. It should be opt-in and independent from
   calendar alerts.

## Later

1. Calendar/focus panel

   ICS support exists in the provider layer, but it is not displayed in the
   compact ops panel by default. Native Google Calendar / Apple Calendar
   integrations are still future work.

2. Docker/OrbStack panel

   Show unhealthy containers, stopped compose projects, and exposed ports.

3. Network panel

   Show WAN status, packet loss, VPN/Tailscale status, or important LAN devices
   online/offline.

4. Alert routing

   Initial support exists for Codex app and Claude Code / Claude Desktop
   interaction alerts. Future work: per-app sound patterns, quiet hours, and
   support for additional apps that expose compatible state logs.

## Open Source Constraints

- Keep all personal configuration in `.env`.
- Keep device IPs, MAC addresses, account ids, tokens, and local paths out of
  tracked files.
- Keep personal/licensed GIFs out of tracked files unless redistribution is
  allowed.
- Prefer provider modules that return generic dictionaries so users can enable
  only the panels they want.
