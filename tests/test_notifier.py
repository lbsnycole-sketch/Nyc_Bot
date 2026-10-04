import json
from unittest.mock import patch, MagicMock
from notifier import (
    PRODUTO,
    format_lote_message,
    format_heartbeat_message,
    format_remocao_message,
    format_resumo_semanal,
    format_alerta_pagina,
    format_pagina_normalizada,
    send_telegram,
    send_telegram_photo,
)


def _lote(titulo="14º lote do Parecer Técnico - ANO-BASE 2024",
          data="16/09/2026", url="https://x/y.pdf", numero="14",
          ano="2024", tipo="Parecer Técnico"):
    return {"titulo": titulo, "data": data, "url": url, "chave": url,
            "numero": numero, "ano": ano, "tipo": tipo}


def test_format_usa_numero_e_tipo_estruturados():
    msg = format_lote_message(_lote())
    assert "14º lote" in msg
    assert "Parecer Técnico" in msg
    assert "Ano-base 2024" in msg
    assert "16/09/2026" in msg


def test_format_cai_para_titulo_sem_numero_ou_tipo():
    msg = format_lote_message(_lote(numero=None, tipo=None))
    assert "14º lote do Parecer Técnico - ANO-BASE 2024" in msg


def test_format_sem_data_nao_quebra():
    msg = format_lote_message(_lote(data=None))
    assert "14º lote" in msg


def test_format_inclui_assinatura_e_contagem():
    msg = format_lote_message(_lote(), acompanhados=14)
    assert PRODUTO in msg
    assert "14 lotes" in msg
    assert "ano-base 2024" in msg


def test_format_assinatura_sempre_presente():
    msg = format_lote_message(_lote())
    assert PRODUTO in msg


def test_format_escapa_html():
    msg = format_lote_message(_lote(titulo="Lote <teste> & 'aspas'", numero=None, tipo=None))
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


def test_heartbeat_mostra_ultima_checagem():
    msg = format_heartbeat_message("15/08/2026", 5, ultima_checagem="04/10/2026 12:00 UTC")
    assert "04/10/2026 12:00 UTC" in msg
    assert "checagem" in msg.lower()


def test_alerta_pagina_inclui_aviso_e_detalhe():
    msg = format_alerta_pagina("Só 0 lote(s) lido(s).")
    assert "⚠️" in msg
    assert "Só 0 lote(s) lido(s)." in msg
    assert "cego" in msg.lower() or "mudou" in msg.lower()


def test_pagina_normalizada():
    msg = format_pagina_normalizada()
    assert "normaliz" in msg.lower()


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


def test_send_telegram_dois_botoes_lado_a_lado():
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    with patch("notifier.requests.post", return_value=fake) as p:
        send_telegram("TOK", "@canal", "oi",
                      buttons=[("A", "https://a.com"), ("B", "https://b.com")])
    markup = json.loads(p.call_args.kwargs["data"]["reply_markup"])
    row = markup["inline_keyboard"][0]
    assert len(row) == 2
    assert row[0]["text"] == "A"
    assert row[1]["url"] == "https://b.com"


def test_send_telegram_photo_faz_post_com_imagem():
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    with patch("notifier.requests.post", return_value=fake) as p:
        send_telegram_photo("TOK", "@canal", b"PNGDATA", caption="resumo")
    url = p.call_args.args[0]
    assert "botTOK/sendPhoto" in url
    assert p.call_args.kwargs["data"]["caption"] == "resumo"
    assert "photo" in p.call_args.kwargs["files"]


def test_send_telegram_photo_repete_e_levanta():
    with patch("notifier.requests.post", side_effect=RuntimeError("boom")), \
         patch("notifier.time.sleep"):
        try:
            send_telegram_photo("TOK", "@canal", b"X", retries=2)
            assert False, "deveria ter levantado"
        except RuntimeError:
            pass


def test_send_telegram_repete_e_levanta_no_fim():
    with patch("notifier.requests.post", side_effect=RuntimeError("boom")), \
         patch("notifier.time.sleep"):
        try:
            send_telegram("TOK", "@canal", "oi", retries=2)
            assert False, "deveria ter levantado"
        except RuntimeError:
            pass
