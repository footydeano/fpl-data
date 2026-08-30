#!/usr/bin/env python3
"""FPL local data puller - stdlib only, no pip deps.

Snapshots the official Fantasy Premier League API to disk:
  data/raw/<UTC stamp>/*.json.gz   immutable historical snapshots
  data/current/*.csv               flat, analysis-ready current state
  data/price_changes.csv           append-only price movement ledger
  data/pull_log.txt                run log

Usage:
  python fpl_pull.py            # standard pull
  python fpl_pull.py --summary  # pull + print a short console summary
"""
import csv
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.environ.get("FPL_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
CUR = os.path.join(DATA, "current")
LOG = os.path.join(DATA, "pull_log.txt")
PRICE_LEDGER = os.path.join(DATA, "price_changes.csv")

BASE = "https://fantasy.premierleague.com/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FPL-local-puller/1.0"
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def log(msg):
    line = "%s  %s" % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"), msg)
    print(line)
    os.makedirs(DATA, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def fetch(path, retries=4):
    url = BASE + path
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = 2 ** attempt
            log("  retry %d/%d for %s after %ss (%s)" % (attempt + 1, retries, path, wait, exc))
            time.sleep(wait)
    raise RuntimeError("failed to fetch %s: %s" % (url, last))


def save_raw(stamp_dir, name, obj):
    os.makedirs(stamp_dir, exist_ok=True)
    dest = os.path.join(stamp_dir, name + ".json.gz")
    with gzip.open(dest, "wt", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    return dest


def write_csv(path, cols, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def read_prev_prices():
    """Map of player id -> now_cost from the last pull, for change detection."""
    prev = {}
    path = os.path.join(CUR, "players.csv")
    if not os.path.exists(path):
        return prev
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                prev[int(row["id"])] = float(row["price"])
    except Exception as exc:  # noqa: BLE001
        log("  WARN could not read previous players.csv: %s" % exc)
    return prev


PLAYER_COLS = [
    "id", "web_name", "full_name", "team", "team_short", "pos", "price",
    "selected_by_percent", "status", "chance_next", "news", "total_points",
    "form", "points_per_game", "minutes", "starts", "goals_scored", "assists",
    "clean_sheets", "goals_conceded", "yellow_cards", "red_cards", "saves",
    "bonus", "bps", "defensive_contribution", "expected_goals",
    "expected_assists", "expected_goal_involvements", "expected_goals_conceded",
    "influence", "creativity", "threat", "ict_index", "ep_this", "ep_next",
    "cost_change_event", "cost_change_start", "transfers_in_event",
    "transfers_out_event", "penalties_order", "corners_order", "freekicks_order",
]


def build_player_rows(boot, teams):
    rows = []
    for e in boot["elements"]:
        t = teams.get(e["team"], {})
        rows.append({
            "id": e["id"],
            "web_name": e.get("web_name"),
            "full_name": ("%s %s" % (e.get("first_name", ""), e.get("second_name", ""))).strip(),
            "team": t.get("name"),
            "team_short": t.get("short_name"),
            "pos": POS.get(e.get("element_type"), "?"),
            "price": e["now_cost"] / 10.0,
            "selected_by_percent": e.get("selected_by_percent"),
            "status": e.get("status"),
            "chance_next": e.get("chance_of_playing_next_round"),
            "news": (e.get("news") or "").replace("\n", " "),
            "total_points": e.get("total_points"),
            "form": e.get("form"),
            "points_per_game": e.get("points_per_game"),
            "minutes": e.get("minutes"),
            "starts": e.get("starts"),
            "goals_scored": e.get("goals_scored"),
            "assists": e.get("assists"),
            "clean_sheets": e.get("clean_sheets"),
            "goals_conceded": e.get("goals_conceded"),
            "yellow_cards": e.get("yellow_cards"),
            "red_cards": e.get("red_cards"),
            "saves": e.get("saves"),
            "bonus": e.get("bonus"),
            "bps": e.get("bps"),
            "defensive_contribution": e.get("defensive_contribution"),
            "expected_goals": e.get("expected_goals"),
            "expected_assists": e.get("expected_assists"),
            "expected_goal_involvements": e.get("expected_goal_involvements"),
            "expected_goals_conceded": e.get("expected_goals_conceded"),
            "influence": e.get("influence"),
            "creativity": e.get("creativity"),
            "threat": e.get("threat"),
            "ict_index": e.get("ict_index"),
            "ep_this": e.get("ep_this"),
            "ep_next": e.get("ep_next"),
            "cost_change_event": e.get("cost_change_event"),
            "cost_change_start": e.get("cost_change_start"),
            "transfers_in_event": e.get("transfers_in_event"),
            "transfers_out_event": e.get("transfers_out_event"),
            "penalties_order": e.get("penalties_order"),
            "corners_order": e.get("corners_and_indirect_freekicks_order"),
            "freekicks_order": e.get("direct_freekicks_order"),
        })
    rows.sort(key=lambda r: (-float(r["price"]), r["web_name"] or ""))
    return rows


def build_fixture_rows(fixtures, teams):
    rows = []
    for f in fixtures:
        h = teams.get(f.get("team_h"), {})
        a = teams.get(f.get("team_a"), {})
        rows.append({
            "id": f.get("id"),
            "gw": f.get("event"),
            "kickoff_utc": f.get("kickoff_time"),
            "home": h.get("short_name"),
            "away": a.get("short_name"),
            "home_fdr": f.get("team_h_difficulty"),
            "away_fdr": f.get("team_a_difficulty"),
            "finished": f.get("finished"),
            "home_score": f.get("team_h_score"),
            "away_score": f.get("team_a_score"),
        })
    rows.sort(key=lambda r: (r["gw"] if r["gw"] is not None else 99, r["kickoff_utc"] or ""))
    return rows


def build_fdr_matrix(fixtures, teams, start_gw, horizon=8):
    """Rows = team, cols = GW n..n+horizon-1, cell = 'OPP(H/A) fdr'."""
    gws = list(range(start_gw, start_gw + horizon))
    grid = {t["short_name"]: {"team": t["short_name"]} for t in teams.values()}
    for f in fixtures:
        gw = f.get("event")
        if gw not in gws:
            continue
        h = teams.get(f.get("team_h"), {}).get("short_name")
        a = teams.get(f.get("team_a"), {}).get("short_name")
        if not h or not a:
            continue
        col = "GW%d" % gw
        hv = "%s(H) %s" % (a, f.get("team_h_difficulty"))
        av = "%s(A) %s" % (h, f.get("team_a_difficulty"))
        grid[h][col] = (grid[h].get(col, "") + " | " + hv).strip(" |")
        grid[a][col] = (grid[a].get(col, "") + " | " + av).strip(" |")
    cols = ["team"] + ["GW%d" % g for g in gws]
    rows = sorted(grid.values(), key=lambda r: r["team"])
    for r in rows:
        for c in cols:
            r.setdefault(c, "BLANK")
    return cols, rows


def log_price_changes(prev, rows, stamp):
    if not prev:
        return 0
    changes = []
    for r in rows:
        old = prev.get(int(r["id"]))
        if old is not None and abs(old - float(r["price"])) > 1e-9:
            changes.append({
                "stamp_utc": stamp, "id": r["id"], "web_name": r["web_name"],
                "team_short": r["team_short"], "pos": r["pos"],
                "old_price": old, "new_price": r["price"],
                "delta": round(float(r["price"]) - old, 1),
                "selected_by_percent": r["selected_by_percent"],
            })
    if not changes:
        return 0
    cols = ["stamp_utc", "id", "web_name", "team_short", "pos", "old_price",
            "new_price", "delta", "selected_by_percent"]
    new_file = not os.path.exists(PRICE_LEDGER)
    with open(PRICE_LEDGER, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for c in changes:
            w.writerow(c)
    return len(changes)


def main():
    t0 = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%MZ")
    stamp_dir = os.path.join(RAW, stamp)
    log("=== FPL pull %s ===" % stamp)

    boot = fetch("/bootstrap-static/")
    fixtures = fetch("/fixtures/")
    save_raw(stamp_dir, "bootstrap-static", boot)
    save_raw(stamp_dir, "fixtures", fixtures)
    log("  raw snapshot -> %s" % stamp_dir)

    teams = {t["id"]: t for t in boot["teams"]}
    events = boot["events"]
    cur = next((e for e in events if e.get("is_current")), None)
    nxt = next((e for e in events if e.get("is_next")), None)
    ref = nxt or cur or events[0]

    prev = read_prev_prices()
    prows = build_player_rows(boot, teams)
    write_csv(os.path.join(CUR, "players.csv"), PLAYER_COLS, prows)
    n_changes = log_price_changes(prev, prows, stamp)

    frows = build_fixture_rows(fixtures, teams)
    write_csv(os.path.join(CUR, "fixtures.csv"),
              ["id", "gw", "kickoff_utc", "home", "away", "home_fdr", "away_fdr",
               "finished", "home_score", "away_score"], frows)

    write_csv(os.path.join(CUR, "teams.csv"),
              ["id", "name", "short_name", "strength", "strength_overall_home",
               "strength_overall_away", "strength_attack_home", "strength_attack_away",
               "strength_defence_home", "strength_defence_away"],
              sorted(teams.values(), key=lambda t: t["id"]))

    write_csv(os.path.join(CUR, "events.csv"),
              ["id", "name", "deadline_time", "finished", "is_current", "is_next",
               "average_entry_score", "highest_score", "most_captained", "most_selected",
               "chip_plays", "transfers_made"],
              [dict(e, chip_plays=json.dumps(e.get("chip_plays", []))) for e in events])

    fcols, fdr = build_fdr_matrix(fixtures, teams, ref["id"], 8)
    write_csv(os.path.join(CUR, "fdr_matrix.csv"), fcols, fdr)
    return boot, teams, events, ref, prows, frows, n_changes, stamp, t0


if __name__ == "__main__":
    try:
        boot, teams, events, ref, prows, frows, n_changes, stamp, t0 = main()
    except Exception as exc:  # noqa: BLE001
        log("FATAL: %s" % exc)
        sys.exit(1)

    meta = {
        "pulled_utc": stamp,
        "reference_gw": ref["id"],
        "reference_gw_deadline_utc": ref.get("deadline_time"),
        "total_players": len(prows),
        "total_fixtures": len(frows),
        "price_changes_since_last_pull": n_changes,
        "total_managers": boot.get("total_players"),
    }
    os.makedirs(CUR, exist_ok=True)
    with open(os.path.join(CUR, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    log("  players=%d fixtures=%d price_changes=%d refGW=%s deadline=%s" % (
        len(prows), len(frows), n_changes, ref["id"], ref.get("deadline_time")))
    log("  done in %.1fs" % (time.time() - t0))

    if "--summary" in sys.argv:
        print("\nTop 15 by ownership:")
        top = sorted(prows, key=lambda r: -float(r["selected_by_percent"] or 0))[:15]
        for r in top:
            print("  %-18s %-4s %-4s %5.1f  %5s%%  %s" % (
                r["web_name"], r["team_short"], r["pos"], r["price"],
                r["selected_by_percent"], r["news"][:40]))
