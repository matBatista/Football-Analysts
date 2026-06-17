"""xT (Expected Threat) contributors — 2018 World Cup Final.

Run from the project root:
    python examples/run_xt.py

Uses the offline StatsBomb cache (sb_cache/events/8658.json).
No network access required after the first run.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import football_metrics as fm
from football_analyst.data import StatsBomb

MATCH_ID = 8658  # France 4-2 Croatia, 2018 FIFA World Cup Final

events = StatsBomb().events(MATCH_ID)

# ── All players, sorted by xT added ──────────────────────────────────────────
print("=" * 52)
print("  xT Contributors — 2018 World Cup Final")
print("  (France 4-2 Croatia, StatsBomb open data)")
print("=" * 52)

top_all = fm.xt_by_player(events).head(15)
print(f"\n{'Rank':<5} {'Player':<28} {'xT Added':>8}")
print("-" * 44)
for rank, row in top_all.iterrows():
    print(f"  {rank + 1:<3} {row['player']:<28} {row['xt_added']:>8.3f}")

# ── Per-team breakdown ────────────────────────────────────────────────────────
print("\n── France (top 5) ──────────────────────────────")
fra = fm.xt_by_player(events, team="France")
for _, row in fra.head(5).iterrows():
    print(f"  {row['player']:<30} {row['xt_added']:.3f}")
print(f"  {'Team total':<30} {fra['xt_added'].sum():.3f}")

print("\n── Croatia (top 5) ─────────────────────────────")
cro = fm.xt_by_player(events, team="Croatia")
for _, row in cro.head(5).iterrows():
    print(f"  {row['player']:<30} {row['xt_added']:.3f}")
print(f"  {'Team total':<30} {cro['xt_added'].sum():.3f}")

# ── Single location lookup ────────────────────────────────────────────────────
print("\n── Location → xT spot-checks ───────────────────")
examples = [
    (0,   40, "Own goal line, centre"),
    (60,  40, "Pitch centre"),
    (90,  40, "Attacking third, centre"),
    (115, 34, "Six-yard box left"),
    (115, 46, "Six-yard box right"),
]
print(f"  {'Location':<30} {'xT':>6}")
print("  " + "-" * 38)
for x, y, label in examples:
    print(f"  ({x:>3},{y:>3})  {label:<22} {fm.location_to_xt(x, y):>6.4f}")

print()
print("Note: Croatia's higher raw xT reflects their 61% possession; France")
print("were more efficient — 4 goals from fewer but more incisive actions.")
