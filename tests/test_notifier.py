from unittest.mock import patch, MagicMock
from notifier import format_lote_message, send_telegram


def test_format_inclui_titulo_e_link():
    lote = {"titulo": "14º lote do Parecer Técnico - ANO-BASE 2024",
            "data": "16/09/2026", "url": "https://x/y.pdf", "chave": "https://x/y.pdf"}
    msg = format_lote_message(lote)
    assert "14º lote do Parecer Técnico" in msg
    assert "16/09/2026" in msg
    assert "https://x/y.pdf" in msg


def test_format_sem_data_nao_quebra():
    lote = {"titulo": "9º lote", "data": None, "url": "https://x/y.pdf", "chave": "https://x/y.pdf"}
    msg = format_lote_message(lote)
    assert "9º lote" in msg
    assert "https://x/y.pdf" in msg


def test_send_telegram_faz_post_correto():
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    with patch("notifier.requests.post", return_value=fake) as p:
        send_telegram("TOK", "@canal", "oi")
    url = p.call_args.args[0]
    assert "botTOK/sendMessage" in url
    data = p.call_args.kwargs["data"]
    assert data["chat_id"] == "@canal"
    assert data["text"] == "oi"


def test_send_telegram_repete_e_levanta_no_fim():
    with patch("notifier.requests.post", side_effect=RuntimeError("boom")) as p, \
         patch("notifier.time.sleep"):
        try:
            send_telegram("TOK", "@canal", "oi", retries=2)
            assert False, "deveria ter levantado"
        except RuntimeError:
            pass
    assert p.call_count == 2
