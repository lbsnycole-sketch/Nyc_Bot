import time
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"


def format_lote_message(lote):
    data = f" ({lote['data']})" if lote.get("data") else ""
    link = lote.get("url") or ""
    linha_link = f"\n📎 {link}" if link else ""
    return f"🆕 Novo lote — Lei do Bem\n{lote['titulo']}{data}{linha_link}".strip()


def send_telegram(token, chat_id, text, retries=3):
    url = _API.format(token=token)
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                url,
                data={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": "false",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err
