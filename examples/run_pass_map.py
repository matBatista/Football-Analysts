"""Generate a pass map. Run from the project root:  python examples/run_pass_map.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import football_analyst as fa

MATCH_ID = 8658  # 2018 World Cup final

# One player...
fa.pass_map(MATCH_ID, player="Antoine Griezmann", save_path="outputs/pass_map_player.png")
# ...or a whole team:
fa.pass_map(MATCH_ID, team="Croatia", save_path="outputs/pass_map_team.png")
print("Saved outputs/pass_map_player.png and outputs/pass_map_team.png")
