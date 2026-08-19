import json
import os
from pathlib import Path

STORAGE_STATE_PATH = Path('/app/playwright_state/storage_state.json')


def get_storage_state() -> dict | None:
    if STORAGE_STATE_PATH.exists():
        with open(STORAGE_STATE_PATH) as f:
            return json.load(f)
    return None


def save_storage_state(state: dict) -> None:
    STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STORAGE_STATE_PATH, 'w') as f:
        json.dump(state, f)


def clear_storage_state() -> None:
    if STORAGE_STATE_PATH.exists():
        STORAGE_STATE_PATH.unlink()
