#!/usr/bin/env python3
"""Real-World Performance Context Engine - schedule, congestion, travel.

Produces per-club, per-gameweek context features that feed the minutes model
and the team-strength adjustment in xp.py. Nothing here scores players directly;
context enters player projections through exactly two channels (P(start) and
team xG/xGA), which is what stops the factors double-counting.

Inputs : data/current/fixtures.csv (from fpl_pull.py) + EURO_MATCHES below.
Outputs: data/current/context.csv
"""
import csv
import math
import os
from datetime import datetime, timedelta

ROOT = os.environ.get("FPL_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
CUR = os.path.join(ROOT, "data", "current")

# Stadium coordinates, approximate to ~1km - adequate for distance banding,
# not for anything requiring precision.
COORDS = {
    "ARS": (51.555, -0.108), "AVL": (52.509, -1.885), "BOU": (50.735, -1.838),
    "BRE": (51.491, -0.289), "BHA": (50.862, -0.084), "CHE": (51.482, -0.191),
    "COV": (52.448, -1.496), "CRY": (51.398, -0.086), "EVE": (53.439, -2.966),
    "FUL": (51.475, -0.222), "HUL": (53.746, -0.368), "IPS": (52.055, 1.145),
    "LEE": (53.778, -1.572), "LIV": (53.431, -2.961), "MCI": (53.483, -2.200),
    "MUN": (53.463, -2.291), "NEW": (54.976, -1.622), "NFO": (52.940, -1.133),
    "TOT": (51.604, -0.066), "SUN": (54.914, -1.388),
}

# European involvement 2026/27. Fill OPPONENTS from the league-phase draw;
# until then travel falls back to a competition-level prior (see travel_km).
EURO_CLUBS = {
    "ARS": "CL", "MCI": "CL", "MUN": "CL", "AVL": "CL", "LIV": "CL",
    "BOU": "EL", "SUN": "EL", "CRY": "EL", "BHA": "UECL",
}
EURO_MATCHES = {  # competition -> [(date, is_home_unknown)] ; dates from UEFA
    "CL":   ["2026-09-10", "2026-10-14", "2026-10-21", "2026-11-04", "2026-11-25",
             "2026-12-09", "2027-01-20", "2027-01-27", "2027-02-17", "2027-02-24",
             "2027-03-10", "2027-03-17", "2027-04-07", "2027-04-14", "2027-04-28",
             "2027-05-05"],
    "EL":   ["2026-09-17", "2026-10-15", "2026-10-22", "2026-11-05", "2026-11-26",
             "2026-12-10", "2027-01-21", "2027-01-28", "2027-02-18", "2027-02-25",
             "2027-03-11", "2027-03-18", "2027-04-08", "2027-04-15", "2027-04-29",
             "2027-05-06"],
    "UECL": ["2026-10-15", "2026-10-22", "2026-11-05", "2026-11-26", "2026-12-10",
             "2026-12-17", "2027-02-18", "2027-02-25", "2027-03-11", "2027-03-18",
             "2027-04-08", "2027-04-15", "2027-04-29", "2027-05-06"],
}
# Median one-way travel for an away leg, by competition. Conservative stand-in
# until the draw is known; replace with real opponent geography when it is.
TRAVEL_PRIOR_KM = {"CL": 1150, "EL": 1400, "UECL": 1600}


def _d(s):
    return datetime.fromisoformat(s[:10]).date()


def haversine(a, b):
    (la1, lo1), (la2, lo2) = a, b
    r = 6371.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 1)


def domestic_travel(club, opponent, is_home):
    if is_home or club not in COORDS or opponent not in COORDS:
        return 0.0
    return haversine(COORDS[club], COORDS[opponent])


def load_fixtures(path=None):
    path = path or os.path.join(CUR, "fixtures.csv")
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if not r["gw"]:
                continue
            rows.append({
                "gw": int(r["gw"]),
                "date": _d(r["kickoff_utc"]) if r["kickoff_utc"] else None,
                "home": r["home"], "away": r["away"],
                "home_fdr": int(r["home_fdr"] or 3),
                "away_fdr": int(r["away_fdr"] or 3),
            })
    return rows


def club_match_dates(fixtures):
    """club -> sorted list of (date, competition, is_home, opponent)."""
    cal = {c: [] for c in COORDS}
    for f in fixtures:
        if f["date"] is None:
            continue
        cal[f["home"]].append((f["date"], "PL", True, f["away"]))
        cal[f["away"]].append((f["date"], "PL", False, f["home"]))
    for club, comp in EURO_CLUBS.items():
        for ds in EURO_MATCHES[comp]:
            # Home/away per leg is unknown until the draw; assume the neutral
            # case (half the legs away) via the travel prior rather than guessing.
            cal[club].append((_d(ds), comp, None, None))
    for c in cal:
        cal[c].sort(key=lambda t: t[0])
    return cal


def congestion_index(rest_days, m7, m14, euro_gap, travel_km):
    """0 (fully rested) to ~1 (extreme load). Calibrated on plausible ranges,
    NOT fitted to outcome data - treat as an ordering device, not a probability.
    Recalibrate against the minutes ledger once ~10 GWs of data exist."""
    rest = max(0.0, min(1.0, (6 - min(rest_days, 6)) / 5.0))      # 6d rest -> 0
    dens = max(0.0, min(1.0, (m14 - 2) / 4.0))                     # 2 in 14d -> 0
    euro = 0.0 if euro_gap is None else max(0.0, min(1.0, (5 - min(euro_gap, 5)) / 4.0))
    trav = max(0.0, min(1.0, travel_km / 2500.0))
    # Weights reflect the evidence: recovery window and European involvement
    # carry most of the signal; travel is real but secondary; raw density least.
    return round(0.34 * rest + 0.34 * euro + 0.20 * trav + 0.12 * dens, 3)


def build(fixtures=None, out=None):
    fixtures = fixtures or load_fixtures()
    cal = club_match_dates(fixtures)
    rows = []
    for f in fixtures:
        if f["date"] is None:
            continue
        for side, club, opp, is_home, fdr in (
            ("H", f["home"], f["away"], True, f["home_fdr"]),
            ("A", f["away"], f["home"], False, f["away_fdr"]),
        ):
            hist = [t for t in cal[club] if t[0] < f["date"]]
            prev = hist[-1][0] if hist else None
            rest = (f["date"] - prev).days if prev else 14
            m7 = sum(1 for t in hist if (f["date"] - t[0]).days <= 7)
            m14 = sum(1 for t in hist if (f["date"] - t[0]).days <= 14)
            m21 = sum(1 for t in hist if (f["date"] - t[0]).days <= 21)
            euros = [t for t in hist if t[1] != "PL" and (f["date"] - t[0]).days <= 6]
            euro_gap = (f["date"] - euros[-1][0]).days if euros else None
            comp = EURO_CLUBS.get(club)
            travel = domestic_travel(club, opp, is_home)
            if euro_gap is not None and comp:
                # Half of European legs are away; charge the prior at 50%.
                travel += TRAVEL_PRIOR_KM[comp] * 0.5
            nxt = [t for t in cal[club] if t[0] > f["date"]]
            rows.append({
                "gw": f["gw"], "club": club, "side": side, "opponent": opp,
                "date": f["date"].isoformat(), "fdr": fdr,
                "rest_days": rest, "m7": m7, "m14": m14, "m21": m21,
                "euro_comp": comp or "", "euro_gap_days": euro_gap if euro_gap is not None else "",
                "travel_km": round(travel, 1),
                "days_to_next": (nxt[0][0] - f["date"]).days if nxt else "",
                "next_is_euro": (nxt[0][1] != "PL") if nxt else "",
                "congestion": congestion_index(rest, m7, m14, euro_gap, travel),
            })
    # Schedule asymmetry: how much more loaded am I than today's opponent?
    by_key = {(r["gw"], r["club"]): r for r in rows}
    for r in rows:
        o = by_key.get((r["gw"], r["opponent"]))
        r["asymmetry"] = round(r["congestion"] - o["congestion"], 3) if o else 0.0
    out = out or os.path.join(CUR, "context.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cols = ["gw", "club", "side", "opponent", "date", "fdr", "rest_days", "m7", "m14",
            "m21", "euro_comp", "euro_gap_days", "travel_km", "days_to_next",
            "next_is_euro", "congestion", "asymmetry"]
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["gw"], r["club"])):
            w.writerow(r)
    return rows


if __name__ == "__main__":
    rs = build()
    print("context rows:", len(rs))
    worst = sorted(rs, key=lambda r: -r["congestion"])[:12]
    print("\nmost congested club-gameweeks")
    for r in worst:
        print("  GW%-2d %-4s %s  rest=%sd euro=%s travel=%skm  load=%.2f asym=%+.2f"
              % (r["gw"], r["club"], r["side"], r["rest_days"],
                 r["euro_gap_days"] or "-", r["travel_km"], r["congestion"], r["asymmetry"]))
