"""Generate a shot map. Run from the project root:  python examples/run_shot_map.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import football_analyst as fa

MATCH_ID = 8658  # 2018 World Cup final: France 4-2 Croatia

fa.shot_map(MATCH_ID, save_path="outputs/shot_map.png")
print("Saved outputs/shot_map.png")
