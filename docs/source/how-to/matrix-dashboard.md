# Matrix dashboard

The matrix dashboard is a glanceable coverage wall: rows are ADI hardware (`hw`
tag), columns are carrier/dev platforms (`platform` tag), and each cell shows the
latest test run's status for that combination. Filter the wall by the boot image
used to test the system (`boot_file` tag).

## Tagging your runs

Cells are built from run tags. When uploading a run, set:

- `hw` — the ADI hardware (e.g. `ad9081`)
- `platform` — the carrier / dev platform (e.g. `zcu102`)
- `boot_file` — the SD-card image used (e.g. `zynqmp-common`)
- `kuiper-linux-release` — (optional) the release (e.g. `2024_R2`); runs with this
  tag appear in the global superset view across all projects.

## Enabling the dashboard

Open the settings area (Tokens page) and click **Enable matrix dashboard**. A
**Matrix** entry appears in your navigation.

## Scopes

- Per project: `/projects/<slug>/matrix` — only that project's boards.
- Global superset: `/matrix` (scope `global`) — every run tagged
  `kuiper-linux-release`, unioned across projects.

## Kiosk / TV mode

Open `/kiosk/matrix?scope=global` in the TV's browser. The page is chrome-less and
auto-refreshes. The browser must hold a logged-in Prism session. Admins can
configure rotation through boot-file filters so one TV cycles several views.

## Admin configuration

On the Admin page, the **Matrix** section configures, per scope:

- `curated_rows` / `curated_cols` — pin boards/platforms that should appear even
  with zero runs (surfacing true coverage gaps).
- `stale_after_hours` — when a cell is flagged stale (default 48).
- `refresh_seconds` — auto-refresh cadence (default 30).
- `rotate_filters` — ordered boot-file values the kiosk cycles through.
