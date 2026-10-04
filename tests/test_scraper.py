from pathlib import Path
from unittest.mock import patch, MagicMock
from scraper import parse_lotes, fetch_html, LOTES_URL

FIXTURE = Path(__file__).parent / "fixtures" / "lotes.html"


def _lotes():
    return parse_lotes(FIXTURE.read_text(encoding="utf-8"))


def test_extrai_lotes_da_fixture():
    lotes = _lotes()
    assert len(lotes) >= 21


def test_cada_lote_tem_chave_e_titulo():
    for l in _lotes():
        assert l["titulo"]
        assert l["chave"]


def test_chaves_sao_unicas():
    lotes = _lotes()
    chaves = [l["chave"] for l in lotes]
    assert len(chaves) == len(set(chaves))


def test_primeiro_lote_esperado():
    lotes = _lotes()
    primeiro = lotes[0]
    assert "14º lote do Parecer Técnico" in primeiro["titulo"]
    assert primeiro["url"].endswith("publicacao-14-lote-parecer-tecnico-2024.pdf")
    assert primeiro["chave"] == primeiro["url"]
    assert primeiro["numero"] == "14"
    assert primeiro["ano"] == "2024"


def test_lotes_tem_campos_numero_ano():
    for l in _lotes():
        assert "numero" in l
        assert "ano" in l


def test_extrai_tipo_simples():
    primeiro = _lotes()[0]
    assert primeiro["tipo"] == "Parecer Técnico"


def test_extrai_tipo_com_parenteses():
    lotes = _lotes()
    rec = next(l for l in lotes if "recurso administrativo" in l["titulo"].lower())
    assert rec["tipo"] == "Parecer Técnico (recurso administrativo)"


def test_tipo_none_quando_formato_desconhecido():
    from scraper import parse_lotes
    html = "<table><tr><td>Lote avulso sem padrão</td></tr></table>"
    lotes = parse_lotes(html)
    assert lotes and lotes[0]["tipo"] is None


def test_fetch_html_usa_get_e_devolve_texto():
    fake = MagicMock()
    fake.text = "<html>ok</html>"
    fake.raise_for_status = MagicMock()
    with patch("scraper.requests.get", return_value=fake) as g:
        out = fetch_html()
    assert out == "<html>ok</html>"
    args, kwargs = g.call_args
    assert args[0] == LOTES_URL
    assert "User-Agent" in kwargs["headers"]
    fake.raise_for_status.assert_called_once()
