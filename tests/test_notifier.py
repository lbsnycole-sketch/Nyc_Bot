import json
from unittest.mock import patch, MagicMock
from notifier import (
    format_lote_message,
    format_heartbeat_message,
    format_remocao_message,
    format_resumo_semanal,
    send_telegram,
)


def _lote(titulo="14º lote do Parecer Técnico - ANO-BASE 2024",
          data="16/09/2026", url="https://x/y.pdf"):
    return {"titulo": titulo, "data": data, "url": url, "chave": url,
            "numero": "14", "ano": "2024"}


def test_format_inclui_titulo_e_data():
    msg = format_lote_message(_lote())
    assert "14º lote do Parecer Técnico" in msg
    assert "16/09/2026" in msg


def test_format_sem_data_nao_quebra():
    lote = _lote(data=None)
    msg = format_lote_message(lote)
    assert "14º lote" in msg


def test_format_inclui_rodape_com_contador():
    msg = format_lote_message(_lote(), total_notificados=3, ultima_notificacao_data="01/08/2026")
    assert "3º notificado" in msg
    assert "01/08/2026" in msg


def test_format_sem_rodape_quando_omitido():
    msg = format_lote_message(_lote())
    assert "notificado" not in msg


def test_format_escapa_html():
    lote = _lote(titulo="Lote <teste> & 'aspas'")
    msg = format_lote_message(lote)
    assert "&lt;teste&gt;" in msg
    assert "&amp;" in msg


def test_heartbeat_inclui_data_e_total():
    msg = format_heartbeat_message("15/08/2026", 5)
    assert "15/08/2026" in msg
    assert "5" in msg
    assert "ativo" in msg.lower()


def test_heartbeat_sem_data():
    msg = format_heartbeat_message(None, 0)
    assert "—" in msg


def test_remocao_inclui_titulo():
    lote = {"chave": "k", "titulo": "Lote removido X"}
    msg = format_remocao_message(lote)
    assert "Lote removido X" in msg
    assert "removido" in msg.lower()


def test_resumo_semanal_com_lotes():
    lotes = [
        {"titulo": "Lote A", "data": "10/09/2026"},
        {"titulo": "Lote B", "data": None},
    ]
    msg = format_resumo_semanal(lotes, 7)
    assert "Lote A" in msg
    assert "Lote B" in msg
    assert "7" in msg


def test_resumo_semanal_vazio():
    msg = format_resumo_semanal([], 3)
    assert "Nenhum lote novo" in msg
    assert "3" in msg


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
    assert data["parse_mode"] == "HTML"


def test_send_telegram_com_botao():
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    with patch("notifier.requests.post", return_value=fake) as p:
        send_telegram("TOK", "@canal", "oi", url_button=("Ver 🔗", "https://x.com"))
    data = p.call_args.kwargs["data"]
    markup = json.loads(data["reply_markup"])
    assert markup["inline_keyboard"][0][0]["url"] == "https://x.com"
    assert markup["inline_keyboard"][0][0]["text"] == "Ver 🔗"


def test_send_telegram_repete_e_levanta_no_fim():
    with patch("notifier.requests.post", side_effect=RuntimeError("boom")), \
         patch("notifier.time.sleep"):
        try:
            send_telegram("TOK", "@canal", "oi", retries=2)
            assert False, "deveria ter levantado"
        except RuntimeError:
            pass
