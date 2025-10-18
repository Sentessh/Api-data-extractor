# src/incremental.py
import json, os, time

STATE_FILE = "state.json"
def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {}

def save_state(state):
    json.dump(state, open(STATE_FILE,"w"))