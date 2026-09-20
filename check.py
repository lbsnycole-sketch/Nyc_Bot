import json
from pathlib import Path

STATE_PATH = Path(__file__).parent / "state.json"


def load_state(path):
    if not Path(path).exists():
        return set()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return set()
    return set(data.get("chaves", []))


def save_state(path, chaves):
    Path(path).write_text(
        json.dumps({"chaves": sorted(chaves)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_new(lotes, known):
    return [l for l in lotes if l["chave"] not in known]
