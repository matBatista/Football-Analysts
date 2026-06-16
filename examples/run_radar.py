"""Generate a player comparison radar.  python examples/run_radar.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import football_analyst as fa

MATCH_IDS = [8658]  # add more match ids for a more reliable per-90 picture

fa.player_radar("Antoine Griezmann", "Luka Modrić", MATCH_IDS,
                save_path="outputs/radar.png")
print("Saved outputs/radar.png")
