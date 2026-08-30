# FPL Context Engine

Drop this folder at `C:\Claude_LOCAL\FPL\tools\engine\`. Requires `fpl_pull.py`
to have run first (needs `data/current/players.csv` and `fixtures.csv`).
Standard library only.

    python tools\engine\selftest.py          # synthetic end-to-end check
    python tools\engine\context.py           # writes data/current/context.csv
    python tools\engine\weekly_scan.py --gw 3

## Modules

| File | Role |
|---|---|
| `context.py` | Per club/gameweek: rest days, match density, European gap, travel km, load index, schedule asymmetry |
| `minutes.py` | P(start), P(sub), P(60), expected minutes, rotation band. `learn_rotation()` replaces priors with observed lineups |
| `xp.py` | Expected points decomposed by scoring rule, incl. bonus and defensive contribution; finishing regressed to xG |
| `decisions.py` | Captaincy (safe/optimal/punt), transfer classifier, bench order, confidence labels |
| `weekly_scan.py` | The A-J gameweek process end to end |

## Architecture

Context never scores a player directly. It enters through two channels only:

    xP = P(start) x E[pts|start] + P(sub) x E[pts|sub]

Channel 1 (minutes): rest, congestion, Europe, travel, squad depth, manager
rotation, team news.
Channel 2 (team rates): opponent quality, venue, tactical matchup.

This is what prevents correlated factors being counted twice.

## Calibration status

Every coefficient is a reasoned PRIOR, not a fit. Recalibrate after ~10
gameweeks of the minutes ledger. Parameters most in need of fitting:

- `context.congestion_index` weights (0.34 / 0.34 / 0.20 / 0.12)
- `minutes.p_start` exposure coefficient (0.55)
- `minutes.ROTATION_PRIOR` per club -> replace via `learn_rotation()`
- `xp.regress_finishing` weight (0.65)
- `xp.expected_bonus` and `expected_defcon` anchors

## Known gaps

- No tactical event data (pressing, line height, transition) - FDR proxies it
- European opponents unknown until the draw; travel uses a competition median
- No backtest yet. Until factors are tested against outcomes, weights are
  reasoning rather than evidence.
