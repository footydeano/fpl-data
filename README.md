# fpl-data

Automated Fantasy Premier League data snapshots. **Private repo.**

A GitHub Action runs `fpl_pull.py` every four hours on GitHub's runners and
commits the results. Nothing here depends on a local machine — that is the
entire point. The Premier League API is not reachable from Claude's cloud
sandbox, but `raw.githubusercontent.com` is, so this repo is the bridge.

## What gets published

| Path | Contents |
|---|---|
| `data/current/players.csv` | ~600 players, 43 columns — price, ownership, xG/xA, xGC, BPS, ICT, defensive contribution, set-piece orders, status and injury news, ep_this/ep_next |
| `data/current/fixtures.csv` | All 380 fixtures, FDR both sides, scores once played |
| `data/current/teams.csv` | Team strength ratings, attack/defence, home/away |
| `data/current/events.csv` | All 38 gameweeks, deadlines, average score, most captained |
| `data/current/fdr_matrix.csv` | Rolling 8-gameweek fixture grid, blank-aware |
| `data/current/meta.json` | Pull timestamp, reference gameweek, row counts |
| `data/price_changes.csv` | Append-only ledger, diffed against the previous pull |
| `data/raw/<stamp>/` | Gzipped API snapshots, pruned after 30 days |

## Reading it

Raw URLs follow this pattern — substitute your own owner and repo:

    https://raw.githubusercontent.com/footydeano/fpl-data/main/data/current/players.csv

For a private repo, raw URLs need a token. If you would rather keep the reads
simple, make the repo public — it contains only public Premier League data and
no personal information.

## Schedule

`0 5 2,6,10,14,18,22 * * *` UTC. The 02:05 run lands just after FPL's 01:30 UTC
price-change lock, so overnight rises and falls are captured the morning they
happen (10:05 AWST).

Run it on demand from the Actions tab via **Run workflow**.
