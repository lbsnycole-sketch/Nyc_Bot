import json
import time
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_lote_message(lote, total_notificados=None, ultima_notificacao_data=None):
    data = f" · {_esc(lote['data'])}" if lote.get("data") else ""
    lines = [
        "🆕 <b>Novo lote — Lei do Bem</b>",
        f"<b>{_esc(lote['titulo'])}</b>{data}",
    ]
    rodape = []
    if total_notificados is not None:
        rodape.append(f"📊 {total_notificados}º notificado")
    if ultima_notificacao_data:
        rodape.append(f"anterior: {_esc(ultima_notificacao_data)}")
    if rodape:
        lines.append("")
        lines.append(" · ".join(rodape))
    return "\n".join(lines)


def format_heartbeat_message(ultima_notificacao_data, total_notificados):
    data = _esc(ultima_notificacao_data) if ultima_notificacao_data else "—"
    return (
        f"✅ <b>Bot ativo — Lei do Bem</b>\n"
        f"Sem novos lotes nos últimos 7 dias.\n"
        f"Última notificação: {data} · Total: {total_notificados} lotes"
    )


def format_remocao_message(lote):
    titulo = _esc(lote.get("titulo") or lote["chave"])
    return (
        f"⚠️ <b>Lote removido da página</b>\n"
        f"{titulo}\n"
        f"<i>Pode ser retificação ou atualização da página oficial.</i>"
    )


def format_resumo_semanal(lotes_semana, total_notificados):
    if not lotes_semana:
        corpo = "Nenhum lote novo esta semana."
    else:
        n = len(lotes_semana)
        items = "\n".join(
            f"• {_esc(l['titulo'])}" + (f" ({_esc(l['data'])})" if l.get("data") else "")
            for l in lotes_semana
        )
        corpo = f"{n} lote{'s' if n > 1 else ''} novo{'s' if n > 1 else ''}:\n{items}"
    return (
        f"📋 <b>Resumo semanal — Lei do Bem</b>\n"
        f"{corpo}\n\n"
        f"Total acumulado: {total_notificados} lotes notificados"
    )


def send_telegram(token, chat_id, text, url_button=None, retries=3):
    url = _API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if url_button:
        label, href = url_button
        payload["reply_markup"] = json.dumps(
            {"inline_keyboard": [[{"text": label, "url": href}]]}
        )
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, data=payload, timeout=30)
            resp.raise_for_status()
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err
