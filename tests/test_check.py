import json
from pathlib import Path
from check import load_state, save_state, find_new
import check as checkmod


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


def _fake_lotes(chaves):
    return [{"titulo": f"lote {c}", "data": "01/01/2026", "url": c, "chave": c} for c in chaves]


def test_seed_salva_sem_notificar(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda *a, **k: enviados.append(a))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    rc = checkmod.main()
    assert rc == 0
    assert enviados == []
    assert checkmod.load_state(state) == {"a", "b"}


def test_notifica_apenas_novos(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, {"a"})
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b", "c"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    rc = checkmod.main()
    assert rc == 0
    assert len(enviados) == 2
    assert checkmod.load_state(state) == {"a", "b", "c"}


def test_falha_de_rede_nao_altera_estado(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, {"a"})
    monkeypatch.setattr(checkmod, "STATE_PATH", state)

    def boom(*a, **k):
        raise RuntimeError("sem internet")

    monkeypatch.setattr(checkmod, "fetch_html", boom)
    rc = checkmod.main()
    assert rc == 0
    assert checkmod.load_state(state) == {"a"}


def test_envio_falho_fica_para_proxima(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, {"a"})
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))

    def boom(*a, **k):
        raise RuntimeError("telegram fora")

    monkeypatch.setattr(checkmod, "send_telegram", boom)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    rc = checkmod.main()
    assert rc == 1
    assert checkmod.load_state(state) == {"a"}


def test_sem_credenciais_com_novos_retorna_1(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, {"a"})
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    rc = checkmod.main()
    assert rc == 1
    assert checkmod.load_state(state) == {"a"}
