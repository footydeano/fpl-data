#!/usr/bin/env python3
"""Captaincy and transfer decision engines.

Captaincy is NOT 'the highest xP player'. It is a rank-optimisation problem:
what matters is xP relative to the field, weighted by effective ownership.
"""

def effective_ownership(selected_pct, captained_pct):
    """EO = ownership + captaincy share (the captain is counted twice)."""
    return round(float(selected_pct or 0) + float(captained_pct or 0), 1)


def captain_rank(candidates, aggression=0.35):
    """candidates: [{name, xp, ceiling, p_start, eo, team, opponent}]

    On pure expected points the answer is always "captain the highest xP" -
    the field's captaincy only shifts the baseline, identically for every
    choice. Ownership matters for the DISTRIBUTION, not the mean: a haul the
    field does not own moves rank far more than one it does.

    So the score is xP plus a share of the upside the field would miss:

        score = xp + aggression * (ceiling - xp) * max(0, 1 - EO/100)

    aggression 0.0  = protect a rank (collapses to highest xP)
    aggression 0.35 = default, chasing
    aggression 0.6  = swinging for a top finish late in the season

    Returns the three answers that genuinely differ.
    """
    out = []
    for c in candidates:
        eo = float(c.get("eo", 5.0))
        xp = float(c["xp"])
        diff = max(0.0, 1.0 - eo / 100.0)
        upside = max(0.0, float(c["ceiling"]) - xp)
        out.append(dict(c, diff_factor=round(diff, 3),
                        score=round(xp + aggression * upside * diff, 2)))

    safe = max(out, key=lambda c: (float(c.get("eo", 0)), c["xp"]))
    optimal = max(out, key=lambda c: c["score"])
    punts = [c for c in out if float(c.get("eo", 100)) < 25 and c["p_start"] >= 0.7]
    punt = max(punts, key=lambda c: c["ceiling"]) if punts else None
    return {"safe": safe, "optimal": optimal, "punt": punt,
            "all": sorted(out, key=lambda c: -c["score"])}


HORIZONS = (1, 3, 5)


def evaluate_transfer(out_player, in_player, xp_out, xp_in, hit=0,
                      notes=None):
    """xp_out / xp_in: lists of xP by gameweek, aligned, length >= 5.

    Classification follows the brief: now / wait / luxury / avoid.
    """
    gains = {h: round(sum(xp_in[:h]) - sum(xp_out[:h]), 2) for h in HORIZONS}
    net5 = gains[5] - hit
    immediate = gains[1] - hit

    if net5 >= 4.0 and immediate >= 0:
        verdict = "DO IT NOW"
    elif net5 >= 4.0 and immediate < 0:
        verdict = "GOOD, BUT WAIT"          # gain is back-loaded; roll instead
    elif 1.5 <= net5 < 4.0:
        verdict = "LUXURY"                   # real but small; not worth a hit
    else:
        verdict = "AVOID"

    return {
        "out": out_player, "in": in_player, "hit": hit,
        "gain_gw": gains[1], "gain_3gw": gains[3], "gain_5gw": gains[5],
        "net_5gw_after_hit": round(net5, 2), "verdict": verdict,
        "notes": notes or [],
    }


def bench_order(bench_projections):
    """Order by P(playing at all) first, xP second - a high-xP player who may
    not start is a worse first sub than a nailed low-xP one."""
    return sorted(bench_projections,
                  key=lambda p: (-(p["p_start"] + p["p_sub"] * 0.5), -p["xp"]))


def confidence(p_start, data_matches, spread=None):
    """Every recommendation carries a confidence label per section 16."""
    if data_matches < 3:
        return "LOW - thin sample, early season"
    if p_start < 0.6:
        return "LOW - minutes uncertain"
    if p_start < 0.8:
        return "MEDIUM"
    return "HIGH"
