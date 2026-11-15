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
         "chave": c, "numero": None, "ano": None, "tipo": None}
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
    assert "Monitor Lei do Bem" in enviados[0]
    assert "01/01/2026" in enviados[0]


def test_botoes_pdf_e_pagina_oficial(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    capturados = []
    monkeypatch.setattr(checkmod, "send_telegram",
                        lambda tok, cid, txt, buttons=None, **k: capturados.append(buttons))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert capturados[0] is not None
    hrefs = [b[1] for b in capturados[0]]
    labels = [b[0] for b in capturados[0]]
    assert "b" in hrefs  # link do PDF do lote
    assert any("oficial" in l.lower() for l in labels)


def test_fmt_data_hora_em_horario_de_brasilia(tmp_path):
    # 12:00 UTC -> 09:00 em Brasília (UTC-3)
    out = checkmod._fmt_data_hora("2026-10-04T12:00:00+00:00")
    assert "09:00" in out
    assert "Brasília" in out


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


def test_heartbeat_nao_repete_apos_enviado(tmp_path, monkeypatch):
    # ultima_notificacao antiga, mas heartbeat ja foi enviado ha pouco:
    # nao deve reenviar (o relogio reseta pelo ultimo_heartbeat).
    state = tmp_path / "state.json"
    ts_antigo = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    ts_heartbeat_recente = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    save_state(state, _make_state({"a"}, ultima_notificacao=ts_antigo,
                                  ultimo_heartbeat=ts_heartbeat_recente))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda *a, **k: enviados.append(a))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert enviados == []


# --- main: resiliência contra cegueira ---

def test_pagina_vazia_e_suspeita_nao_altera_estado_nem_heartbeat(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    ts_antigo = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    save_state(state, _make_state({"a", "b", "c", "d"}, ultima_notificacao=ts_antigo))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: [])
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda *a, **k: enviados.append(a))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    s = checkmod.load_state(state)
    assert enviados == []  # nao mente "Bot ativo"
    assert set(s["chaves"]) == {"a", "b", "c", "d"}
    assert s["falhas_consecutivas"] == 1


def test_pagina_encolhida_e_suspeita(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda *a, **k: enviados.append(a))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    s = checkmod.load_state(state)
    assert enviados == []
    assert s["falhas_consecutivas"] == 1
    assert len(s["chaves"]) == 10


def test_alerta_enviado_uma_vez_apos_limite(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b", "c", "d"}, falhas_consecutivas=2))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: [])
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    # 3a falha consecutiva -> alerta
    checkmod.main()
    assert len(enviados) == 1
    assert "⚠️" in enviados[0]
    s = checkmod.load_state(state)
    assert s["falhas_consecutivas"] == 3
    assert s["alerta_pagina_enviado"] is True
    # 4a falha -> NAO repete o alerta
    checkmod.main()
    assert len(enviados) == 1
    assert checkmod.load_state(state)["falhas_consecutivas"] == 4


def test_recuperacao_apos_alerta(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b", "c", "d"}, falhas_consecutivas=5,
                                  alerta_pagina_enviado=True))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b", "c", "d"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    s = checkmod.load_state(state)
    assert any("normaliz" in m.lower() for m in enviados)
    assert s["falhas_consecutivas"] == 0
    assert s["alerta_pagina_enviado"] is False
    assert s["ultima_checagem_ok"] is not None


def test_troca_em_massa_alerta_sem_spam(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b", "c", "d"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["w", "x", "y", "z"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    s = checkmod.load_state(state)
    assert len(enviados) == 1  # um alerta, nao 8 mensagens
    assert "⚠️" in enviados[0]
    assert set(s["chaves"]) == {"a", "b", "c", "d"}  # nao marca os novos como vistos


def test_lote_em_massa_legitimo_notifica_normal(tmp_path, monkeypatch):
    # muitos novos, zero removidos -> nao e troca de formato, notifica normal
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b", "c", "d"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes",
                        lambda h: _fake_lotes(["a", "b", "c", "d", "e", "f", "g"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    s = checkmod.load_state(state)
    assert len(enviados) == 3  # e, f, g
    assert set(s["chaves"]) == {"a", "b", "c", "d", "e", "f", "g"}


def test_heartbeat_mostra_ultima_checagem_ok(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    ts_antigo = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    ts_checagem = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    save_state(state, _make_state({"a"}, ultima_notificacao=ts_antigo,
                                  ultima_checagem_ok=ts_checagem))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert len(enviados) == 1
    assert "checagem" in enviados[0].lower()


def test_scrape_confiavel_atualiza_ultima_checagem_ok(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a"}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a"]))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    s = checkmod.load_state(state)
    assert s["ultima_checagem_ok"] is not None


# --- main: remoção ---

def test_remocao_transitoria_nao_notifica_na_primeira_ausencia(tmp_path, monkeypatch):
    # Uma unica leitura confiavel sem o lote "b" NAO pode disparar remocao:
    # o gov.br as vezes renderiza uma linha a menos. Aguarda confirmacao.
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
    assert not any("removido" in m.lower() for m in enviados)
    s = checkmod.load_state(state)
    assert "b" in s["lotes_ativos"]            # mantido, aguardando confirmacao
    assert s["remocoes_pendentes"].get("b") == 1


def test_lote_reaparece_cancela_remocao_pendente(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b"}, remocoes_pendentes={"b": 1}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert not any("removido" in m.lower() for m in enviados)
    assert checkmod.load_state(state)["remocoes_pendentes"] == {}


def test_remocao_notificada_apos_confirmacao(tmp_path, monkeypatch):
    # Lote ausente pela 2a leitura seguida -> remocao confirmada e notificada.
    state = tmp_path / "state.json"
    save_state(state, _make_state({"a", "b"}, remocoes_pendentes={"b": 1}))
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    checkmod.main()
    assert any("removido" in m.lower() for m in enviados)
    s = checkmod.load_state(state)
    assert "b" not in s["lotes_ativos"]
    assert "b" not in s["remocoes_pendentes"]


def test_remocao_notificada_em_duas_execucoes(tmp_path, monkeypatch):
    # Integracao: duas leituras seguidas sem "b" -> so a 2a notifica.
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
    assert not any("removido" in m.lower() for m in enviados)
    checkmod.main()
    assert any("removido" in m.lower() for m in enviados)
