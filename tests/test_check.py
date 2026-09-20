import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from check import load_state, save_state, find_new, find_removed, _default_state
import check as checkmod


def _make_state(chaves, **extra):
    s = _default_state()
    s["chaves"] = sorted(chaves)
    s["lotes_ativos"] = sorted(chaves)
    s.update(extra)
    return s


def _fake_lotes(chaves):
    return [
        {"titulo": f"lote {c}", "data": "01/01/2026", "url": c,
         "chave": c, "numero": None, "ano": None}
        for c in chaves
    ]


# --- load/save ---

def test_load_state_ausente_retorna_default(tmp_path):
    s = load_state(tmp_path / "nao_existe.json")
    assert s["chaves"] == []
    assert s["total_notificados"] == 0


def test_load_state_invalido_retorna_default(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("isso nao e json", encoding="utf-8")
    s = load_state(p)
    assert s["chaves"] == []


def test_save_e_load_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = _make_state({"b", "a"}, total_notificados=2)
    save_state(p, s)
    s2 = load_state(p)
    assert set(s2["chaves"]) == {"a", "b"}
    assert s2["total_notificados"] == 2
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["chaves"] == ["a", "b"]


def test_load_backward_compat_formato_antigo(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"chaves": ["x", "y"]}), encoding="utf-8")
    s = load_state(p)
    assert set(s["chaves"]) == {"x", "y"}
    assert set(s["lotes_ativos"]) == {"x", "y"}
    assert s["total_notificados"] == 0


def test_find_new_retorna_apenas_desconhecidos():
    lotes = [{"chave": "x"}, {"chave": "y"}, {"chave": "z"}]
    novos = find_new(lotes, {"x"})
    assert [l["chave"] for l in novos] == ["y", "z"]


def test_find_new_vazio_quando_tudo_conhecido():
    lotes = [{"chave": "x"}]
    assert find_new(lotes, {"x"}) == []


def test_find_removed():
    assert find_removed(["a", "b"], {"a", "c"}) == ["b"]
    assert find_removed(["a"], {"a", "b"}) == []
    assert find_removed([], {"a"}) == []


# --- main: seed ---

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
    assert set(checkmod.load_state(state)["chaves"]) == {"a", "b"}


# --- main: notificações ---

def test_notifica_apenas_novos(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}))
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
    assert set(checkmod.load_state(state)["chaves"]) == {"a", "b", "c"}


def test_notifica_com_contador_e_historico(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}, total_notificados=1, ultima_notificacao_data="01/01/2026"))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    s = checkmod.load_state(state)
    assert s["total_notificados"] == 2
    assert len(s["historico"]) == 1
    assert "2º notificado" in enviados[0]
    assert "01/01/2026" in enviados[0]


def test_botao_url_enviado_quando_ha_link(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    botoes = []
    monkeypatch.setattr(checkmod, "send_telegram",
                        lambda tok, cid, txt, url_button=None, **k: botoes.append(url_button))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert botoes[0] is not None
    assert botoes[0][1] == "b"


# --- main: erros e resiliência ---

def test_falha_de_rede_nao_altera_estado(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sem internet")))
    rc = checkmod.main()
    assert rc == 0
    assert set(checkmod.load_state(state)["chaves"]) == {"a"}


def test_envio_falho_fica_para_proxima(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    monkeypatch.setattr(checkmod, "send_telegram",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("telegram fora")))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    rc = checkmod.main()
    assert rc == 1
    assert set(checkmod.load_state(state)["chaves"]) == {"a"}


def test_sem_credenciais_com_novos_retorna_1(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    rc = checkmod.main()
    assert rc == 1
    assert set(checkmod.load_state(state)["chaves"]) == {"a"}


# --- main: heartbeat ---

def test_heartbeat_enviado_apos_30_dias(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    ts_antigo = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    save_state(state, _make_state({"a"}, ultima_notificacao=ts_antigo,
                                   ultima_notificacao_data="01/07/2026",
                                   total_notificados=3))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    rc = checkmod.main()
    assert rc == 0
    assert len(enviados) == 1
    assert "ativo" in enviados[0].lower()


def test_heartbeat_nao_enviado_antes_de_30_dias(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    ts_recente = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    save_state(state, _make_state({"a"}, ultima_notificacao=ts_recente))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda *a, **k: enviados.append(a))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert enviados == []


# --- main: remoção ---

def test_remocao_notificada(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert any("removido" in m.lower() for m in enviados)


# --- resumo semanal ---

def test_resumo_semanal_sem_credenciais(tmp_path, monkeypatch):
    monkeypatch.setattr(checkmod, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    rc = checkmod.resumo_semanal()
    assert rc == 1


def test_resumo_semanal_envia_mensagem(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    ts_hoje = datetime.now(timezone.utc).isoformat()
    s = _make_state({"a"}, total_notificados=1, historico=[
        {"chave": "a", "titulo": "Lote A", "data": "20/09/2026",
         "url": "a", "numero": None, "ano": None, "notificado_em": ts_hoje}
    ])
    save_state(state, s)
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    rc = checkmod.resumo_semanal()
    assert rc == 0
    assert "Lote A" in enviados[0]
