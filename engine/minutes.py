#!/usr/bin/env python3
"""Expected-minutes / rotation-risk model.

The core claim of the upgrade: context does not act on a player's scoring rate
so much as on whether he is on the pitch. Everything schedule-related enters
here, once, so it cannot be double-counted downstream.

Outputs per player: p_start, p_sub, p_60 (the appearance-point threshold),
xmins, and a rotation_risk band for reporting.
"""
import csv
import os

ROOT = os.environ.get("FPL_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
CUR = os.path.join(ROOT, "data", "current")

# Manager/club rotation propensity, 0 = never rotates, 1 = rotates heavily.
# Prior only. Overwrite from the observed lineup ledger once it exists -
# see learn_rotation() below. Evidence anchor: European clubs average 2.5 XI
# changes per matchday vs 1.9 for non-European clubs.
ROTATION_PRIOR = {
    "MCI": 0.75, "CHE": 0.70, "LIV": 0.60, "ARS": 0.55, "MUN": 0.55,
    "TOT": 0.55, "AVL": 0.55, "NEW": 0.50, "BHA": 0.65, "CRY": 0.45,
    "BOU": 0.45, "SUN": 0.45, "EVE": 0.40, "NFO": 0.40, "FUL": 0.40,
    "BRE": 0.40, "LEE": 0.40, "COV": 0.40, "HUL": 0.40, "IPS": 0.40,
}
DEFAULT_ROTATION = 0.45

# A start is worth ~82 minutes on average; a benched appearance ~18.
MINS_IF_START = 82.0
MINS_IF_SUB = 18.0


def f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def availability_gate(status, chance):
    """Hard availability multiplier from official FPL flags."""
    if status in ("i", "s", "u", "n"):          # injured, suspended, unavailable
        return 0.0
    if status == "d":                            # doubtful
        c = f(chance, 50.0)
        return max(0.0, min(1.0, c / 100.0))
    return 1.0


def importance(player, squad):
    """Share of the club's minutes at this position - a proxy for how nailed
    the player is. Returns 0..1."""
    peers = [p for p in squad if p["pos"] == player["pos"]]
    tot = sum(f(p["minutes"]) for p in peers) or 1.0
    share = f(player["minutes"]) / tot
    top = max(f(p["minutes"]) for p in peers) or 1.0
    rel = f(player["minutes"]) / top
    return max(0.0, min(1.0, 0.5 * min(share * len(peers) / 2.0, 1.0) + 0.5 * rel))


# Early-season shrinkage. Two pseudo-matches at a 0.60 prior stop a single
# observation swinging the estimate to 0 or 1 - with three league games played,
# raw rates are almost pure noise. Converges to the observed rate as data grows.
PRIOR_START_RATE = 0.60
PRIOR_WEIGHT = 2.0


def base_start_rate(player, matches_played):
    """Starts per team match, shrunk toward a prior while the sample is thin.

    matches_played MUST be the number of matches the club has actually
    finished, not the gameweek number. Passing gw-1 during a part-played
    gameweek makes every nailed starter look like a rotation risk.
    """
    if matches_played <= 0:
        return PRIOR_START_RATE
    starts = f(player["starts"])
    if starts <= 0:
        # New signing or no starts field yet: infer from minutes.
        mins = f(player["minutes"])
        starts = min(matches_played, mins / 90.0)
    a = starts + PRIOR_WEIGHT * PRIOR_START_RATE
    b = matches_played + PRIOR_WEIGHT
    return max(0.0, min(1.0, a / b))


def p_start(player, squad, congestion, matches_played, rotation=None,
            recent_consecutive_starts=None):
    gate = availability_gate(player.get("status", "a"), player.get("chance_next"))
    if gate == 0.0:
        return 0.0
    base = base_start_rate(player, matches_played)
    imp = importance(player, squad)
    rot = ROTATION_PRIOR.get(player.get("team_short"), DEFAULT_ROTATION) \
        if rotation is None else rotation

    # Congestion pushes the squad toward its rotation propensity, and it bites
    # hardest on players who are not nailed. A fully nailed player (imp=1) is
    # largely immune; a squad player is highly exposed.
    exposure = (1.0 - imp) * rot * congestion
    p = base * (1.0 - 0.55 * exposure)

    # Consecutive starts through a congested run raise the odds of a rest.
    if recent_consecutive_starts and congestion > 0.4:
        p *= 1.0 - min(0.12, 0.03 * max(0, recent_consecutive_starts - 3))

    return max(0.0, min(0.99, p * gate))


def project(player, squad, congestion, matches_played, **kw):
    ps = p_start(player, squad, congestion, matches_played, **kw)
    gate = availability_gate(player.get("status", "a"), player.get("chance_next"))
    # Sub appearances are likelier for fringe players, and likelier still when
    # the manager is rotating.
    imp = importance(player, squad)
    psub = max(0.0, min(1.0 - ps, (1.0 - ps) * (0.30 + 0.35 * (1.0 - imp)))) * gate
    xmins = ps * MINS_IF_START + psub * MINS_IF_SUB
    # P(reaching 60 minutes) - the 2-point appearance threshold.
    p60 = ps * 0.82 + psub * 0.06
    if ps >= 0.75:
        band = "nailed"
    elif ps >= 0.55:
        band = "likely"
    elif ps >= 0.30:
        band = "rotation risk"
    elif ps > 0.0:
        band = "fringe"
    else:
        band = "unavailable"
    return {"p_start": round(ps, 3), "p_sub": round(psub, 3), "p_60": round(p60, 3),
            "xmins": round(xmins, 1), "rotation_risk": band}


def learn_rotation(lineup_ledger):
    """Replace the priors with observed behaviour.

    lineup_ledger: iterable of {club, gw, xi_changes_vs_prev}. Returns
    club -> propensity scaled so 1.9 changes/match ~ 0.40 and 3.5 ~ 0.85,
    matching the observed European/non-European split.
    """
    agg = {}
    for r in lineup_ledger:
        agg.setdefault(r["club"], []).append(f(r["xi_changes_vs_prev"]))
    out = {}
    for club, vals in agg.items():
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        out[club] = round(max(0.15, min(0.95, 0.40 + (mean - 1.9) * 0.28)), 3)
    return out
