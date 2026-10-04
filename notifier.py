import json
import time
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"
_API_PHOTO = "https://api.telegram.org/bot{token}/sendPhoto"

# Identidade do produto (marca neutra; trocar aqui se quiser outra assinatura).
PRODUTO = "Monitor Lei do Bem"

_ICON_LOTE = "📄"
_ICON_OK = "✅"
_ICON_ALERTA = "⚠️"
_ICON_RESUMO = "📋"


def _esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _assinatura(acompanhados=None, ano=None):
    partes = [PRODUTO]
    if acompanhados:
        plural = "lotes" if acompanhados != 1 else "lote"
        trecho = f"{acompanhados} {plural}"
        if ano:
            trecho += f" · ano-base {_esc(ano)}"
        partes.append(trecho)
    return " · ".join(partes)


def format_lote_message(lote, acompanhados=None):
    numero = lote.get("numero")
    tipo = lote.get("tipo")
    if numero and tipo:
        corpo = f"{_esc(numero)}º lote · {_esc(tipo)}"
    else:
        corpo = _esc(lote["titulo"])

    meta = []
    if lote.get("ano"):
        meta.append(f"Ano-base {_esc(lote['ano'])}")
    if lote.get("data"):
        meta.append(_esc(lote["data"]))

    linhas = [f"{_ICON_LOTE} <b>Novo lote — Lei do Bem</b>", "", f"<b>{corpo}</b>"]
    if meta:
        linhas.append(" · ".join(meta))
    linhas += ["", _assinatura(acompanhados, lote.get("ano"))]
    return "\n".join(linhas)


def format_heartbeat_message(ultima_notificacao_data, total_notificados, ultima_checagem=None):
    data = _esc(ultima_notificacao_data) if ultima_notificacao_data else "—"
    linhas = [
        f"{_ICON_OK} <b>Bot ativo — Lei do Bem</b>",
        "",
        "Sem novos lotes nos últimos 7 dias.",
    ]
    if ultima_checagem:
        linhas.append(f"Última checagem: {_esc(ultima_checagem)}")
    linhas.append(f"Última notificação: {data}")
    linhas += ["", _assinatura(total_notificados)]
    return "\n".join(linhas)


def format_remocao_message(lote):
    numero = lote.get("numero")
    tipo = lote.get("tipo")
    if numero and tipo:
        corpo = f"{_esc(numero)}º lote · {_esc(tipo)}"
    else:
        corpo = _esc(lote.get("titulo") or lote["chave"])
    return "\n".join([
        f"{_ICON_ALERTA} <b>Lote removido da página — Lei do Bem</b>",
        "",
        f"<b>{corpo}</b>",
        "<i>Pode ser retificação ou atualização da página oficial.</i>",
        "",
        _assinatura(),
    ])


def format_alerta_pagina(detalhe):
    return "\n".join([
        f"{_ICON_ALERTA} <b>Página da Lei do Bem pode ter mudado</b>",
        "",
        "O bot pode estar cego — a leitura da página saiu do esperado.",
        _esc(detalhe),
        "<i>Vale conferir a página oficial manualmente.</i>",
        "",
        _assinatura(),
    ])


def format_pagina_normalizada():
    return "\n".join([
        f"{_ICON_OK} <b>Monitoramento normalizado</b>",
        "",
        "A leitura da página da Lei do Bem voltou ao normal.",
        "",
        _assinatura(),
    ])


def format_resumo_semanal(lotes_semana, total_notificados):
    if not lotes_semana:
        corpo = "Nenhum lote novo esta semana."
    else:
        n = len(lotes_semana)
        plural = "s" if n > 1 else ""
        items = "\n".join(
            f"• <b>{_esc(l['titulo'])}</b>"
            + (f" ({_esc(l['data'])})" if l.get("data") else "")
            for l in lotes_semana
        )
        corpo = f"{n} lote{plural} novo{plural} esta semana:\n{items}"
    return "\n".join([
        f"{_ICON_RESUMO} <b>Resumo semanal — Lei do Bem</b>",
        "",
        corpo,
        "",
        _assinatura(total_notificados),
    ])


def _keyboard(buttons):
    return json.dumps(
        {"inline_keyboard": [[{"text": label, "url": href} for label, href in buttons]]}
    )


def _botoes(url_button, buttons):
    if buttons:
        return list(buttons)
    if url_button:
        return [url_button]
    return []


def send_telegram(token, chat_id, text, url_button=None, buttons=None, retries=3):
    url = _API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    botoes = _botoes(url_button, buttons)
    if botoes:
        payload["reply_markup"] = _keyboard(botoes)
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


def send_telegram_photo(token, chat_id, image, caption=None, buttons=None, retries=3):
    url = _API_PHOTO.format(token=token)
    data = {"chat_id": chat_id, "parse_mode": "HTML"}
    if caption:
        data["caption"] = caption
    if buttons:
        data["reply_markup"] = _keyboard(buttons)
    last_err = None
    for attempt in range(retries):
        try:
            files = {"photo": ("grafico.png", image, "image/png")}
            resp = requests.post(url, data=data, files=files, timeout=60)
            resp.raise_for_status()
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err
