import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from scraper import fetch_html, parse_lotes, LOTES_URL
from notifier import (
    send_telegram,
    format_lote_message,
    format_heartbeat_message,
    format_remocao_message,
    format_resumo_semanal,
)

STATE_PATH = Path(__file__).parent / "state.json"
_HEARTBEAT_DAYS = 30
_SEMANAL_DAYS = 7


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_state():
    return {
        "chaves": [],
        "lotes_ativos": [],
        "historico": [],
        "total_notificados": 0,
        "ultima_notificacao": None,
        "ultima_notificacao_data": None,
        "ultimo_heartbeat": None,
    }


def load_state(path):
    if not Path(path).exists():
        return _default_state()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return _default_state()
    state = _default_state()
    state["chaves"] = list(data.get("chaves", []))
    state["lotes_ativos"] = list(data.get("lotes_ativos", state["chaves"]))
    state["historico"] = list(data.get("historico", []))
    state["total_notificados"] = int(data.get("total_notificados", 0))
    state["ultima_notificacao"] = data.get("ultima_notificacao")
    state["ultima_notificacao_data"] = data.get("ultima_notificacao_data")
    state["ultimo_heartbeat"] = data.get("ultimo_heartbeat")
    return state


def save_state(path, state):
    out = {**state, "chaves": sorted(state["chaves"])}
    Path(path).write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_new(lotes, known_chaves):
    known = set(known_chaves)
    return [l for l in lotes if l["chave"] not in known]


def find_removed(lotes_ativos_prev, current_chaves):
    current = set(current_chaves)
    return [c for c in lotes_ativos_prev if c not in current]


def _parse_iso(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _needs_heartbeat(state):
    ref = state.get("ultima_notificacao") or state.get("ultimo_heartbeat")
    dt = _parse_iso(ref)
    if not dt:
        return False
    return (datetime.now(timezone.utc) - dt).days >= _HEARTBEAT_DAYS


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

    state = load_state(STATE_PATH)
    current_chaves = {l["chave"] for l in lotes}

    if not state["chaves"]:
        state["chaves"] = sorted(current_chaves)
        state["lotes_ativos"] = sorted(current_chaves)
        save_state(STATE_PATH, state)
        print(f"[seed] estado inicial salvo com {len(lotes)} lotes (sem notificar).")
        return 0

    novos = find_new(lotes, state["chaves"])
    removed = find_removed(state["lotes_ativos"], current_chaves)
    heartbeat = _needs_heartbeat(state) and not novos

    if not novos and not removed and not heartbeat:
        state["lotes_ativos"] = sorted(current_chaves)
        save_state(STATE_PATH, state)
        print("[ok] nenhum lote novo.")
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[erro] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ausentes; nao consigo notificar.")
        return 1

    falhas = 0
    ultima_data_ref = state.get("ultima_notificacao_data")
    notificados_chaves = set()

    for lote in novos:
        try:
            contador = state["total_notificados"] + len(notificados_chaves) + 1
            msg = format_lote_message(
                lote,
                total_notificados=contador,
                ultima_notificacao_data=ultima_data_ref,
            )
            btn = ("Ver lote 🔗", lote["url"]) if lote.get("url") else None
            send_telegram(token, chat_id, msg, url_button=btn)
            notificados_chaves.add(lote["chave"])
            ultima_data_ref = lote.get("data")
            state["historico"].append({
                "chave": lote["chave"],
                "titulo": lote["titulo"],
                "data": lote.get("data"),
                "url": lote.get("url"),
                "numero": lote.get("numero"),
                "ano": lote.get("ano"),
                "notificado_em": _now_iso(),
            })
            print(f"[novo] notificado: {lote['titulo']}")
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"[erro] falha ao notificar {lote['titulo']}: {e}")

    if notificados_chaves:
        state["total_notificados"] += len(notificados_chaves)
        state["chaves"] = sorted(set(state["chaves"]) | notificados_chaves)
        state["ultima_notificacao"] = _now_iso()
        state["ultima_notificacao_data"] = ultima_data_ref

    for chave in removed:
        lote_info = next(
            (h for h in reversed(state["historico"]) if h["chave"] == chave),
            {"chave": chave},
        )
        try:
            send_telegram(token, chat_id, format_remocao_message(lote_info))
            print(f"[removido] {chave}")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] falha ao notificar remocao {chave}: {e}")

    if heartbeat:
        try:
            msg = format_heartbeat_message(
                state.get("ultima_notificacao_data"),
                state["total_notificados"],
            )
            send_telegram(token, chat_id, msg)
            state["ultimo_heartbeat"] = _now_iso()
            print("[heartbeat] mensagem enviada.")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] falha ao enviar heartbeat: {e}")

    state["lotes_ativos"] = sorted(current_chaves)
    save_state(STATE_PATH, state)
    print(f"[ok] {len(novos)} novo(s); {len(removed)} removido(s); {falhas} falha(s).")
    return 1 if falhas else 0


def resumo_semanal():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[erro] credenciais ausentes.")
        return 1

    state = load_state(STATE_PATH)
    corte = datetime.now(timezone.utc) - timedelta(days=_SEMANAL_DAYS)
    lotes_semana = [
        h for h in state["historico"]
        if (dt := _parse_iso(h.get("notificado_em"))) and dt >= corte
    ]
    msg = format_resumo_semanal(lotes_semana, state["total_notificados"])
    try:
        send_telegram(token, chat_id, msg)
        print(f"[resumo] enviado com {len(lotes_semana)} lote(s) da semana.")
    except Exception as e:  # noqa: BLE001
        print(f"[erro] falha ao enviar resumo: {e}")
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--resumo-semanal":
        sys.exit(resumo_semanal())
    sys.exit(main())
