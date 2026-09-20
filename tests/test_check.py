import json
from pathlib import Path
from check import load_state, save_state, find_new


def test_load_state_ausente_retorna_vazio(tmp_path):
    assert load_state(tmp_path / "nao_existe.json") == set()


def test_load_state_invalido_retorna_vazio(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("isso nao e json", encoding="utf-8")
    assert load_state(p) == set()


def test_save_e_load_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    save_state(p, {"b", "a"})
    assert load_state(p) == {"a", "b"}
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["chaves"] == ["a", "b"]


def test_find_new_retorna_apenas_desconhecidos():
    lotes = [{"chave": "x"}, {"chave": "y"}, {"chave": "z"}]
    novos = find_new(lotes, {"x"})
    assert [l["chave"] for l in novos] == ["y", "z"]


def test_find_new_vazio_quando_tudo_conhecido():
    lotes = [{"chave": "x"}]
    assert find_new(lotes, {"x"}) == []
