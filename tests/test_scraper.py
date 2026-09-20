from pathlib import Path
from scraper import parse_lotes

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
