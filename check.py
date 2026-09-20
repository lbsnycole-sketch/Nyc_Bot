import json
import os
import sys
from pathlib import Path

from scraper import fetch_html, parse_lotes, LOTES_URL
from notifier import send_telegram, format_lote_message

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


def main():
    try:
        html = fetch_html()
        lotes = parse_lotes(html)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] falha ao baixar/ler a pagina: {e}")
        return 0

    if not lotes:
        print("[warn] nenhum lote extraido; pagina possivelmente incompleta. Nada a fazer.")
        return 0

    known = load_state(STATE_PATH)

    if not known:
        save_state(STATE_PATH, {l["chave"] for l in lotes})
        print(f"[seed] estado inicial salvo com {len(lotes)} lotes (sem notificar).")
        return 0

    novos = find_new(lotes, known)
    if not novos:
        print("[ok] nenhum lote novo.")
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[erro] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ausentes; nao consigo notificar.")
        return 1

    notificados = set()
    falhas = 0
    for lote in novos:
        try:
            msg = format_lote_message(lote) + f"\n\nFonte: {LOTES_URL}"
            send_telegram(token, chat_id, msg)
            notificados.add(lote["chave"])
            print(f"[novo] notificado: {lote['titulo']}")
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"[erro] falha ao notificar {lote['titulo']}: {e}")

    save_state(STATE_PATH, known | notificados)
    print(f"[ok] {len(notificados)} novo(s) notificado(s); {falhas} falha(s).")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
