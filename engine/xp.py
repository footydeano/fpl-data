#!/usr/bin/env python3
"""Expected-points model with explicit FPL scoring decomposition.

xP = P(start) * E[pts | start] + P(sub) * E[pts | sub]

E[pts | start] is built from the actual scoring rules rather than a single
blended number, because the components respond to different inputs:

  appearance + goals + assists + clean sheet/goals conceded + saves
  + defensive contribution + bonus - cards

Two components the brief did not mention are carried here deliberately:
BONUS (BPS) and DEFENSIVE CONTRIBUTION. Between them they are a large share of
a defender's or holding midfielder's return and are routinely under-modelled.
"""
import math

POINTS_GOAL = {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}
POINTS_CS = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
POINTS_ASSIST = 3
DEFCON_POINTS = 2
DEFCON_THRESHOLD = {"DEF": 10, "MID": 12, "FWD": 12, "GKP": 99}


def poisson_zero(lmbda):
    return math.exp(-lmbda)


def clean_sheet_prob(team_xga):
    """P(0 goals conceded) under a Poisson goals-against model."""
    return poisson_zero(max(0.05, team_xga))


def expected_goals_conceded_penalty(team_xga):
    """FPL deducts 1 point per 2 goals conceded (GKP/DEF). Expected deduction
    over a Poisson with mean team_xga."""
    return -0.5 * team_xga


def fixture_multiplier(fdr, is_home):
    """Convert FPL difficulty into an attacking-rate multiplier.
    FDR 2 -> ~1.18, FDR 3 -> ~1.00, FDR 5 -> ~0.72. Home bonus ~+6%."""
    m = 1.0 + (3 - fdr) * 0.09
    return m * (1.06 if is_home else 0.96)


def regress_finishing(goals, xg, matches, weight=0.65):
    """Finishing regresses hard. Blend observed goals toward xG - form-chasing
    on overperformance is the most common expensive FPL error."""
    if matches <= 0:
        return xg
    return weight * xg + (1 - weight) * goals


def expected_bonus(bps_per_90, xmins):
    """Crude but useful: BPS per 90 maps to expected bonus points. Anchored so
    ~28 BPS/90 (a regular bonus contender) yields ~0.8 bonus points per start."""
    if xmins <= 0:
        return 0.0
    scaled = max(0.0, (bps_per_90 - 14.0) / 18.0)
    return round(min(1.6, 0.8 * scaled) * (xmins / 90.0), 3)


def expected_defcon(defcon_per_90, pos, xmins):
    """P(hitting the defensive-contribution threshold) x 2 points."""
    thr = DEFCON_THRESHOLD.get(pos, 99)
    if thr > 50 or xmins <= 0:
        return 0.0
    scaled = defcon_per_90 * (xmins / 90.0)
    # Logistic around the threshold; sd ~ 3.2 contributions.
    p = 1.0 / (1.0 + math.exp(-(scaled - thr) / 3.2))
    return round(p * DEFCON_POINTS, 3)


def points_if_start(p, mins_model, team_ctx):
    """p: player row. team_ctx: {'xg_for','xga','fdr','is_home'}."""
    pos = p["pos"]
    mult = fixture_multiplier(team_ctx["fdr"], team_ctx["is_home"])
    per90 = lambda k: (float(p.get(k) or 0) / max(1.0, float(p.get("minutes") or 0)) * 90.0) \
        if float(p.get("minutes") or 0) > 0 else 0.0

    xg90 = regress_finishing(per90("goals_scored"), per90("expected_goals"),
                             float(p.get("starts") or 0)) * mult
    xa90 = per90("expected_assists") * mult

    pts = 2.0                                   # 60+ minute appearance
    pts += xg90 * POINTS_GOAL.get(pos, 4)
    pts += xa90 * POINTS_ASSIST

    if pos in ("GKP", "DEF", "MID"):
        cs = clean_sheet_prob(team_ctx["xga"])
        pts += cs * POINTS_CS.get(pos, 0)
    if pos in ("GKP", "DEF"):
        pts += expected_goals_conceded_penalty(team_ctx["xga"])
    if pos == "GKP":
        pts += per90("saves") / 3.0

    pts += expected_defcon(per90("defensive_contribution"), pos, 90.0)
    pts += expected_bonus(per90("bps"), 90.0)
    pts -= per90("yellow_cards") * 1.0 + per90("red_cards") * 3.0
    return max(0.0, pts)


def expected_points(p, mins, team_ctx):
    """mins: output of minutes.project(). Returns xP and its decomposition."""
    start_pts = points_if_start(p, mins, team_ctx)
    # A substitute gets the 1-point appearance and a fraction of attacking output.
    sub_pts = 1.0 + 0.20 * max(0.0, start_pts - 2.0)
    xp = mins["p_start"] * start_pts + mins["p_sub"] * sub_pts
    return {
        "xp": round(xp, 2),
        "pts_if_start": round(start_pts, 2),
        "p_start": mins["p_start"],
        "xmins": mins["xmins"],
        "rotation_risk": mins["rotation_risk"],
        # Ceiling matters for captaincy: roughly, the 90th-percentile outcome.
        "ceiling": round(mins["p_start"] * (start_pts * 2.6 + 1.5), 2),
    }
