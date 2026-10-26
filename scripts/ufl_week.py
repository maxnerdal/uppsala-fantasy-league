# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Uppsala Fantasy League: the numbers behind the Monday article.

all-play, the closest matchups and which free agent would have flipped them,
and category projections for next week from each team's best possible weekly lineup.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yahoo_nba as y  # noqa: E402

CATS = ["FGM", "FG%", "FTM", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"]
COUNTING = ["FGM", "FGA", "FTM", "FTA", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"]


def totals(stats):
    t = {k: stats.get(k) or 0.0 for k in COUNTING}
    t["FG%"] = t["FGM"] / t["FGA"] if t["FGA"] else 0.0
    t["FT%"] = t["FTM"] / t["FTA"] if t["FTA"] else 0.0
    return t


def with_attempts(s):
    s = dict(s)
    for m, a, pct in (("FGM", "FGA", "FG%"), ("FTM", "FTA", "FT%")):
        if s.get(a) is None:
            s[a] = round(s[m] / s[pct]) if s.get(m) and s.get(pct) else 0.0
    return s


def add(a, b, sign=1):
    return totals({k: (a.get(k) or 0) + sign * (b.get(k) or 0) for k in COUNTING})


def compare(a, b):
    w = l = 0
    margins = []
    for c in CATS:
        x, z = a[c], b[c]
        if c == "TO":
            x, z = -x, -z
        if x > z:
            w += 1
        elif x < z:
            l += 1
        rel = abs(a[c] - b[c]) / max(abs(a[c]), abs(b[c]), 1e-9)
        margins.append((round(rel, 4), c))
    return w, l, sorted(margins)


def all_play(teams):
    out = []
    for name, t in teams.items():
        rec = [0, 0, 0]
        for other, o in teams.items():
            if other == name:
                continue
            w, l, _ = compare(t, o)
            rec[0 if w > l else 1 if l > w else 2] += 1
        out.append({"team": name, "w": rec[0], "l": rec[1], "t": rec[2]})
    return sorted(out, key=lambda r: (-r["w"], r["l"]))


def ranks(teams):
    out = {n: {} for n in teams}
    for c in CATS:
        order = sorted(teams, key=lambda n: teams[n][c], reverse=(c != "TO"))
        for i, n in enumerate(order, 1):
            out[n][c] = i
    return out


def flips(loser_tot, winner_tot, loser_players, fas):
    """Free agents whose full week, in place of one player's counted stats, wins the matchup.

    Player rows on the matchup page hold only what counted for the team, so they sum to the team total.
    """
    found = []
    starters = [p for p in loser_players if p["stats"].get("PTS") is not None]
    for fa in fas:
        fs = with_attempts(fa["stats"])
        best = None
        for s in starters:
            new = add(add(loser_tot, with_attempts(s["stats"]), -1), fs)
            w, l, _ = compare(new, winner_tot)
            if w > l and (best is None or (w - l) > best["diff"]):
                best = {"diff": w - l, "score": f"{w}-{l}", "replaces": s["name"]}
        if best:
            found.append({"add": fa["name"], "team": fa["team"], "owned": fa["percent_owned"], "gp": fa["stats"].get("GP"),
                          "week": {k: fa["stats"].get(k) for k in CATS}} | best)
    return sorted(found, key=lambda f: (-f["diff"], f["owned"]))[:5]


def projected_rosters(lid, team_ids):
    out = {}
    for tid in team_ids:
        name, players = y.team_roster(lid, tid)
        proj = {p["id"]: with_attempts(p["stats"]) for p in y.players_list(lid, "S_PS7", status="ALL", fteam=tid)}
        out[name] = [p | {"proj": proj[p["id"]]} for p in players
                     if p["id"] in proj and p.get("selected") not in ("IL", "IL+", "NA")
                     and p.get("status") not in y.NOT_STARTABLE]
    return out


def best_lineups(rosters, slots):
    """Each team's starters if the manager sets the lineup that maximises projected value.

    Lineups are weekly, so only starters score. Value is the z-score sum of a player's projected week
    across all candidates in the league, with FG% and FT% as impact (makes above league rate).
    """
    pool = [p for ps in rosters.values() for p in ps]
    fg = sum(p["proj"].get("FGM") or 0 for p in pool) / max(sum(p["proj"].get("FGA") or 0 for p in pool), 1)
    ft = sum(p["proj"].get("FTM") or 0 for p in pool) / max(sum(p["proj"].get("FTA") or 0 for p in pool), 1)

    def line(p):
        s = p["proj"]
        return {"FGM": s.get("FGM") or 0, "FG%": (s.get("FGM") or 0) - fg * (s.get("FGA") or 0),
                "FTM": s.get("FTM") or 0, "FT%": (s.get("FTM") or 0) - ft * (s.get("FTA") or 0)} | \
               {k: s.get(k) or 0 for k in ("3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO")}

    lines = [line(p) for p in pool]
    mu = {c: sum(l[c] for l in lines) / len(lines) for c in CATS}
    sd = {c: (sum((l[c] - mu[c]) ** 2 for l in lines) / len(lines)) ** 0.5 or 1 for c in CATS}
    value = lambda p: sum((line(p)[c] - mu[c]) / sd[c] * (-1 if c == "TO" else 1) for c in CATS)

    slots = tuple(s for s in slots if s not in y.RESERVE_SLOTS)
    out = {}
    for name, ps in rosters.items():
        cands = tuple(sorted(((p, 100 + value(p)) for p in ps), key=lambda c: -c[1]))
        start = y.optimize(cands, slots)
        starters = [p for p in ps if p["id"] in start]
        sums = {k: sum(p["proj"].get(k) or 0 for p in starters) for k in COUNTING}
        out[name] = {"totals": totals(sums), "starters": [p["name"] for p in starters],
                     "bench": [p["name"] for p in ps if p["id"] not in start]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", required=True, type=int)
    ap.add_argument("--fa-count", type=int, default=75)
    args = ap.parse_args()
    lid = y.load_config()["YAHOO_NBA_LEAGUE_ID"]

    home = y.league_home(lid, args.week)
    details = [y.matchup(lid, m["mid1"], m["week"]) for m in home["matchups"]]
    teams, rosters, games = {}, {}, []
    for d in details:
        a, b = d["teams"]
        for side, t in zip(("me", "opponent"), (a, b)):
            teams[t["name"]] = totals(t["stats"])
            rosters[t["name"]] = d["players"][side]
        games.append((a["name"], b["name"]))

    # Last 7 days (total) equals the finished week when run on Monday before the first game (US Eastern).
    fas = y.available(lid, "S_L7", args.fa_count)
    gp = {p["name"]: p["stats"].get("GP") for m in home["matchups"] for tid in (m["mid1"], m["mid2"])
          for p in y.players_list(lid, "S_L7", status="ALL", fteam=tid)}

    matchups = []
    for a, b in games:
        w, l, margins = compare(teams[a], teams[b])
        winner, loser = (a, b) if w > l else (b, a) if l > w else (None, None)
        m = {"teams": [a, b], "score": f"{w}-{l}", "closest_categories": margins[:4]}
        if winner:
            m["winner"] = winner
            m["flips"] = flips(teams[loser], teams[winner], rosters[loser], fas)
        matchups.append(m)
    matchups.sort(key=lambda m: (abs(int(m["score"].split("-")[0]) - int(m["score"].split("-")[1])),
                                 sum(x for x, _ in m["closest_categories"][:3])))

    players = []
    for team, ps in rosters.items():
        for p in ps:
            if p["stats"].get("PTS") is not None:
                players.append({"team": team, "name": p["name"], "slot": p.get("selected"), "gp": gp.get(p["name"]),
                                "rank_current": p.get("rank_current"), "stats": p["stats"]})

    nxt = y.league_home(lid, args.week + 1)
    ids = [t for m in nxt["matchups"] for t in (m["mid1"], m["mid2"])]
    lineups = best_lineups(projected_rosters(lid, ids), y.settings(lid)["roster_slots"])
    by_id = {t["id"]: t["team"] for t in nxt["standings"]}
    upcoming = []
    for m in nxt["matchups"]:
        na, nb = by_id[m["mid1"]], by_id[m["mid2"]]
        pa, pb = lineups[na]["totals"], lineups[nb]["totals"]
        w, l, margins = compare(pa, pb)
        upcoming.append({"teams": [na, nb], "projected": f"{w}-{l}",
                         "favourite": na if w > l else nb if l > w else None,
                         "swing": [c for _, c in margins[:3]],
                         "proj": {n: {c: round(t[c], 3) for c in CATS} for n, t in ((na, pa), (nb, pb))},
                         "lineups": {n: {k: lineups[n][k] for k in ("starters", "bench")} for n in (na, nb)}})

    out = {"week": args.week, "standings": home["standings"],
           "totals": {n: {c: round(t[c], 3) for c in CATS} for n, t in teams.items()},
           "category_ranks": ranks(teams), "all_play": all_play(teams),
           "matchups": matchups, "players": players, "next_week": upcoming}
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
