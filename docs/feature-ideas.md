# Feature Ideas

Prioritized ideas for turning the Times Gate into a small ambient operations
panel.

## Near Term

1. Local resources panel

   Show CPU, memory, disk, battery, and thermal pressure. This can use macOS
   built-ins first (`ps`, `vm_stat`, `df`, `pmset`, `osx-cpu-temp` when
   available), then optionally `psutil` for portability.

2. Service health panel

   Track a short list of local URLs and ports, for example `localhost:3000`,
   `localhost:8000`, a local API, or the Divoom asset server.

3. AI spend panel

   Show OpenAI and Anthropic daily/monthly spend, plus projected end-of-month
   spend. This should be off by default because it may require API keys.

4. GitHub work panel

   Show failing CI, open PRs waiting for review, or the latest deploy status.
   Keep tokens in `.env` or an OS keychain, never in the repo.

## Later

1. Calendar/focus panel

   Show next meeting countdown, focus mode, or "do not disturb" state.

2. Docker/OrbStack panel

   Show unhealthy containers, stopped compose projects, and exposed ports.

3. Network panel

   Show WAN status, packet loss, VPN/Tailscale status, or important LAN devices
   online/offline.

4. Alert routing

   Use the Divoom buzzer for urgent transitions and silent animations for low
   priority status changes.

## Open Source Constraints

- Keep all personal configuration in `.env`.
- Keep device IPs, MAC addresses, account ids, tokens, and local paths out of
  tracked files.
- Keep personal/licensed GIFs out of tracked files unless redistribution is
  allowed.
- Prefer provider modules that return generic dictionaries so users can enable
  only the panels they want.
