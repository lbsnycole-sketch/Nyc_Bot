# Lei do Bem — Notificador de Lotes Novos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Postar num canal do Telegram sempre que um lote novo aparecer na página de lotes da Lei do Bem, rodando de hora em hora no GitHub Actions, 100% grátis e sem servidor.

**Architecture:** Um script Python roda no cron do GitHub Actions: baixa a página de lotes, extrai a lista de lotes (chave = URL do PDF), compara com `state.json` versionado no repositório e posta no Telegram os que forem novos. Sem banco de dados, sem servidor, sem cadastro de inscritos.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4`, `pytest` (dev), GitHub Actions, Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-09-20-lei-do-bem-lote-notifier-design.md`

## Global Constraints

- Fonte: `https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/lei-do-bem/paginas/lotes`
- Chave única de cada lote: a **URL do PDF** (`<a href>` da linha); fallback `"{titulo}|{data}"` se não houver link.
- **Só adições notificam.** Nunca notificar por remoção/ausência.
- **Primeira execução (estado vazio) = seed:** salva estado, não notifica.
- Falha de rede ou página sem lotes: **não altera estado, não notifica, sai com código 0.**
- Segredos lidos do ambiente: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Nunca hardcodar.
- Nomes de função estáveis: `parse_lotes`, `fetch_html`, `LOTES_URL`, `format_lote_message`, `send_telegram`, `load_state`, `save_state`, `find_new`, `main`.

---

## File Structure

- `scraper.py` — download + parsing da página. Responsável só por transformar HTML em lista de lotes.
- `notifier.py` — formatação e envio da mensagem ao Telegram.
- `check.py` — orquestração: estado, diff, seed, envio. Ponto de entrada.
- `state.json` — memória dos lotes já vistos (versionado).
- `requirements.txt` — dependências de runtime.
- `.github/workflows/check.yml` — agendador (cron horário) + commit do estado.
- `.gitignore` — ignora artefatos Python.
- `README.md` — passo a passo de configuração (BotFather, canal, repo, secrets).
- `tests/fixtures/lotes.html` — cópia real da página para teste do parser.
- `tests/test_scraper.py`, `tests/test_notifier.py`, `tests/test_check.py`.

---

### Task 1: Scaffolding, dependências e fixture de teste

**Files:**
- Create: `requirements.txt`, `.gitignore`, `tests/fixtures/lotes.html`
- Init: repositório git

**Interfaces:**
- Consumes: nada.
- Produces: repo git inicializado; `tests/fixtures/lotes.html` (HTML real da página); dependências instaláveis.

- [ ] **Step 1: Inicializar git e estrutura**

```bash
cd /home/guilherme/Desktop/LeiDoBemKPMG
git init
mkdir -p tests/fixtures .github/workflows
```

- [ ] **Step 2: Criar `requirements.txt`**

```
requests>=2.31
beautifulsoup4>=4.12
```

- [ ] **Step 3: Criar `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
```

- [ ] **Step 4: Salvar a fixture real (HTML já baixado nesta sessão)**

```bash
cp "/tmp/claude-1000/-home-guilherme-Desktop-LeiDoBemKPMG/f4954926-2915-441d-b7fd-a1fbf8e2e9c7/scratchpad/lotes.html" tests/fixtures/lotes.html
```

Se o arquivo do scratchpad não existir mais, rebaixar:
```bash
curl -sL -A "Mozilla/5.0" "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/lei-do-bem/paginas/lotes" -o tests/fixtures/lotes.html
```

- [ ] **Step 5: Instalar dependências (para os testes seguintes)**

```bash
pip install -r requirements.txt pytest
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore tests/fixtures/lotes.html
git commit -m "chore: scaffolding, deps e fixture de teste"
```

---

### Task 2: Parser da página (`parse_lotes`)

**Files:**
- Create: `scraper.py`
- Test: `tests/test_scraper.py`

**Interfaces:**
- Consumes: `tests/fixtures/lotes.html`.
- Produces:
  - `LOTES_URL: str`
  - `parse_lotes(html: str) -> list[dict]` — cada dict tem chaves `titulo: str`, `data: str | None`, `url: str | None`, `chave: str`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_scraper.py`:
```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: Implementar `scraper.py` (parte do parser)**

```python
import re
from bs4 import BeautifulSoup

LOTES_URL = "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/lei-do-bem/paginas/lotes"

_LOTE_RE = re.compile(r"\blote\b", re.I)
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")


def parse_lotes(html):
    soup = BeautifulSoup(html, "html.parser")
    lotes = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        titulo = tds[0].get_text(" ", strip=True)
        if not _LOTE_RE.search(titulo):
            continue
        row_text = tr.get_text(" ", strip=True)
        m = _DATE_RE.search(row_text)
        data = m.group(1) if m else None
        a = tr.find("a", href=True)
        url = a["href"] if a else None
        chave = url or f"{titulo}|{data}"
        lotes.append({"titulo": titulo, "data": data, "url": url, "chave": chave})
    return lotes
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: parser dos lotes da pagina Lei do Bem"
```

---

### Task 3: Download da página (`fetch_html`)

**Files:**
- Modify: `scraper.py`
- Test: `tests/test_scraper.py`

**Interfaces:**
- Consumes: `LOTES_URL`.
- Produces: `fetch_html(url: str = LOTES_URL, timeout: int = 30) -> str` — faz GET com User-Agent, levanta em erro HTTP, devolve o texto.

- [ ] **Step 1: Escrever o teste que falha (com `requests` mockado)**

Adicionar a `tests/test_scraper.py`:
```python
from unittest.mock import patch, MagicMock
from scraper import fetch_html, LOTES_URL

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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `python -m pytest tests/test_scraper.py::test_fetch_html_usa_get_e_devolve_texto -v`
Expected: FAIL com `ImportError: cannot import name 'fetch_html'`

- [ ] **Step 3: Implementar `fetch_html` em `scraper.py`**

Adicionar no topo dos imports: `import requests`
E a função:
```python
def fetch_html(url=LOTES_URL, timeout=30):
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (LeiDoBemBot)"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: download da pagina de lotes"
```

---

### Task 4: Estado e diff (`load_state`, `save_state`, `find_new`)

**Files:**
- Create: `check.py`
- Test: `tests/test_check.py`

**Interfaces:**
- Consumes: nada externo.
- Produces:
  - `load_state(path: Path) -> set[str]` — lê `{"chaves": [...]}`; retorna set vazio se arquivo ausente/inválido.
  - `save_state(path: Path, chaves) -> None` — grava `{"chaves": [ordenadas]}` em JSON UTF-8.
  - `find_new(lotes: list[dict], known: set[str]) -> list[dict]` — lotes cujo `chave` não está em `known`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_check.py`:
```python
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
    # gravado ordenado
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["chaves"] == ["a", "b"]

def test_find_new_retorna_apenas_desconhecidos():
    lotes = [{"chave": "x"}, {"chave": "y"}, {"chave": "z"}]
    novos = find_new(lotes, {"x"})
    assert [l["chave"] for l in novos] == ["y", "z"]

def test_find_new_vazio_quando_tudo_conhecido():
    lotes = [{"chave": "x"}]
    assert find_new(lotes, {"x"}) == []
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `python -m pytest tests/test_check.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'check'`

- [ ] **Step 3: Implementar as funções de estado em `check.py`**

```python
import json
import os
import sys
from pathlib import Path

from scraper import fetch_html, parse_lotes, LOTES_URL
from notifier import send_telegram, format_lote_message

STATE_PATH = Path(__file__).parent / "state.json"


def load_state(path):
    if not Path(path).exists():
        return set()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return set()
    return set(data.get("chaves", []))


def save_state(path, chaves):
    Path(path).write_text(
        json.dumps({"chaves": sorted(chaves)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_new(lotes, known):
    return [l for l in lotes if l["chave"] not in known]
```

Nota: o import de `notifier` é necessário para a Task 6; a Task 5 cria esse módulo. Se executar os testes desta task antes da Task 5, comente temporariamente a linha `from notifier import ...` — ela volta na Task 6. (Executando em ordem, faça a Task 5 e depois volte; mas os testes de estado desta task não dependem de `notifier`.)

Para manter a Task 4 verde de forma independente, **não** inclua o import de `notifier` ainda. Adicione apenas:
```python
import json
from pathlib import Path
```
Os demais imports (`os`, `sys`, `scraper`, `notifier`) entram na Task 6.

- [ ] **Step 4: Rodar e verificar que passa**

Run: `python -m pytest tests/test_check.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add check.py tests/test_check.py
git commit -m "feat: estado e diff de lotes"
```

---

### Task 5: Notificador Telegram (`format_lote_message`, `send_telegram`)

**Files:**
- Create: `notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Consumes: nada externo.
- Produces:
  - `format_lote_message(lote: dict) -> str` — monta o texto a partir de `titulo`, `data`, `url`.
  - `send_telegram(token: str, chat_id: str, text: str, retries: int = 3) -> None` — POST em `sendMessage`; repete em falha; levanta o último erro se esgotar.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_notifier.py`:
```python
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
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'notifier'`

- [ ] **Step 3: Implementar `notifier.py`**

```python
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
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "feat: notificador do Telegram"
```

---

### Task 6: Orquestração (`main`) com seed e resiliência

**Files:**
- Modify: `check.py`
- Test: `tests/test_check.py`

**Interfaces:**
- Consumes: `fetch_html`, `parse_lotes`, `LOTES_URL` (scraper); `send_telegram`, `format_lote_message` (notifier); `load_state`, `save_state`, `find_new`.
- Produces: `main() -> int` — código de saída (0 ok/seed/sem-novos; 1 se faltou credencial ou algum envio falhou).

Regras:
- Falha em `fetch_html`/`parse_lotes` ou lista vazia → não altera estado, retorna 0.
- Estado vazio (seed) → salva todas as chaves atuais, não notifica, retorna 0.
- Sem novos → retorna 0.
- Há novos mas faltam `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` → retorna 1 (não altera estado).
- Para cada novo: envia; sucesso entra no estado, falha é excluída (retry na próxima). Estado final = `known | notificados_com_sucesso`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar a `tests/test_check.py`:
```python
import check as checkmod

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
    assert enviados == []                       # seed nao notifica
    assert checkmod.load_state(state) == {"a", "b"}

def test_notifica_apenas_novos(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    checkmod.save_state(state, {"a"})           # ja conhece "a"
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b", "c"]))
    enviados = []
    monkeypatch.setattr(checkmod, "send_telegram", lambda tok, cid, txt, **k: enviados.append(txt))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@c")
    rc = checkmod.main()
    assert rc == 0
    assert len(enviados) == 2                    # b e c
    assert checkmod.load_state(state) == {"a", "b", "c"}

def test_falha_de_rede_nao_altera_estado(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    checkmod.save_state(state, {"a"})
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    def boom(*a, **k):
        raise RuntimeError("sem internet")
    monkeypatch.setattr(checkmod, "fetch_html", boom)
    rc = checkmod.main()
    assert rc == 0
    assert checkmod.load_state(state) == {"a"}

def test_envio_falho_fica_para_proxima(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    checkmod.save_state(state, {"a"})
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
    assert checkmod.load_state(state) == {"a"}   # "b" nao entrou (vai tentar de novo)

def test_sem_credenciais_com_novos_retorna_1(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    checkmod.save_state(state, {"a"})
    monkeypatch.setattr(checkmod, "STATE_PATH", state)
    monkeypatch.setattr(checkmod, "fetch_html", lambda *a, **k: "<html/>")
    monkeypatch.setattr(checkmod, "parse_lotes", lambda h: _fake_lotes(["a", "b"]))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    rc = checkmod.main()
    assert rc == 1
    assert checkmod.load_state(state) == {"a"}
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `python -m pytest tests/test_check.py -k "seed or notifica or rede or falho or credenciais" -v`
Expected: FAIL com `AttributeError: module 'check' has no attribute 'main'` (ou erro de import de `notifier`/`fetch_html`)

- [ ] **Step 3: Completar `check.py`**

Ajustar os imports do topo (substituir o bloco mínimo da Task 4) para:
```python
import json
import os
import sys
from pathlib import Path

from scraper import fetch_html, parse_lotes, LOTES_URL
from notifier import send_telegram, format_lote_message
```

E adicionar ao final do arquivo:
```python
def main():
    try:
        html = fetch_html()
        lotes = parse_lotes(html)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] falha ao baixar/ler a pagina: {e}")
        return 0

    if not lotes:
        print("[warn] nenhum lote extraido; pagina possivelmente incompleta. Nada a fazer.")
        return 0

    known = load_state(STATE_PATH)

    if not known:
        save_state(STATE_PATH, {l["chave"] for l in lotes})
        print(f"[seed] estado inicial salvo com {len(lotes)} lotes (sem notificar).")
        return 0

    novos = find_new(lotes, known)
    if not novos:
        print("[ok] nenhum lote novo.")
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[erro] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ausentes; nao consigo notificar.")
        return 1

    notificados = set()
    falhas = 0
    for lote in novos:
        try:
            msg = format_lote_message(lote) + f"\n\nFonte: {LOTES_URL}"
            send_telegram(token, chat_id, msg)
            notificados.add(lote["chave"])
            print(f"[novo] notificado: {lote['titulo']}")
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"[erro] falha ao notificar {lote['titulo']}: {e}")

    save_state(STATE_PATH, known | notificados)
    print(f"[ok] {len(notificados)} novo(s) notificado(s); {falhas} falha(s).")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `python -m pytest -v`
Expected: PASS (todos: scraper 5, notifier 4, check 10)

- [ ] **Step 5: Commit**

```bash
git add check.py tests/test_check.py
git commit -m "feat: orquestracao main com seed e resiliencia"
```

---

### Task 7: Workflow do GitHub Actions + README

**Files:**
- Create: `.github/workflows/check.yml`, `README.md`

**Interfaces:**
- Consumes: `check.py`, `requirements.txt`, segredos `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`.
- Produces: automação agendada; documentação de setup.

- [ ] **Step 1: Criar `.github/workflows/check.yml`**

```yaml
name: Checar lotes Lei do Bem

on:
  schedule:
    - cron: "0 * * * *"      # toda hora (horario UTC)
  workflow_dispatch: {}        # permite rodar manualmente pelo botao "Run workflow"

permissions:
  contents: write              # para commitar state.json

concurrency:
  group: checar-lotes
  cancel-in-progress: false

jobs:
  checar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Instalar dependencias
        run: pip install -r requirements.txt

      - name: Rodar verificacao
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python check.py

      - name: Commitar estado se mudou
        run: |
          git add state.json
          if git diff --cached --quiet; then
            echo "state.json inalterado"
          else
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git commit -m "chore: atualizar estado dos lotes"
            git push
          fi
```

- [ ] **Step 2: Criar `README.md`**

````markdown
# Aviso de Lotes — Lei do Bem (Telegram)

Bot que avisa num canal do Telegram sempre que um **lote novo** é publicado na
página de lotes da Lei do Bem do MCTI. Roda sozinho no GitHub Actions, de hora
em hora. 100% grátis, sem servidor.

## Como funciona

A cada hora o GitHub Actions baixa a [página de lotes](https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/lei-do-bem/paginas/lotes),
compara com o que já viu (`state.json`) e posta no canal do Telegram os lotes novos.

## Configuração (uma vez, ~5 min)

### 1. Criar o bot do Telegram
1. No Telegram, abra conversa com **@BotFather**.
2. Envie `/newbot` e siga as instruções (nome + username terminando em `bot`).
3. Ele devolve um **token** parecido com `123456:ABC-DEF...`. Guarde.

### 2. Criar o canal e adicionar o bot
1. Crie um **canal** no Telegram (pode ser público ou privado).
2. Em *Administradores*, adicione o seu bot como **administrador** (com permissão
   de postar mensagens).
3. Descubra o `chat_id`:
   - **Canal público:** use `@nomedocanal` (o username do canal).
   - **Canal privado:** poste algo, encaminhe uma mensagem do canal para o bot
     **@userinfobot** ou acesse
     `https://api.telegram.org/bot<TOKEN>/getUpdates` depois de postar algo, e
     copie o `chat.id` (algo como `-1001234567890`).

### 3. Subir para o GitHub e configurar segredos
1. Crie um repositório e suba estes arquivos.
2. Em **Settings → Secrets and variables → Actions → New repository secret**,
   crie:
   - `TELEGRAM_BOT_TOKEN` = o token do BotFather
   - `TELEGRAM_CHAT_ID` = `@nomedocanal` ou o id numérico
3. Em **Settings → Actions → General**, garanta que Actions está habilitado e que
   *Workflow permissions* está em **Read and write**.

### 4. Rodar a primeira vez
- Vá em **Actions → Checar lotes Lei do Bem → Run workflow**.
- A **primeira** execução só grava o estado atual (não envia nada) — é o esperado.
- Da próxima vez que sair um lote novo, o canal recebe o aviso.

## Convidar outras pessoas
Basta compartilhar o **link de convite do canal**. Quem entrar passa a receber os avisos.

## Rodar/testar localmente
```bash
pip install -r requirements.txt pytest
python -m pytest -v            # testes
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=@canal python check.py
```

## Ajustar a frequência
No arquivo `.github/workflows/check.yml`, mude a linha `cron`. Ex.: `"0 */6 * * *"`
= a cada 6 horas. (Horário em UTC; o cron do GitHub pode atrasar alguns minutos.)
````

- [ ] **Step 3: Verificar o YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/check.yml'))" 2>/dev/null || echo "instale pyyaml para validar, ou revise manualmente"`
Expected: sem erro (ou revisão manual da indentação)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/check.yml README.md
git commit -m "ci: workflow agendado e documentacao de setup"
```

---

## Notas de execução / verificação final

- Rode `python -m pytest -v` — devem passar 19 testes.
- `state.json` **não** é criado pelos testes; ele nasce na primeira execução real
  do `check.py` (seed). Está correto o repositório começar sem ele.
- O envio real ao Telegram só é validado quando o usuário configurar os segredos
  e rodar o workflow (ou rodar localmente com token/chat_id). Isso está fora do
  escopo dos testes automatizados por depender de credenciais do usuário.

## Self-Review (feito)

- **Cobertura da spec:** fonte/parser (T2), download (T3), estado+diff (T4),
  seed e "só adições" e resiliência a rede/erro (T6), notificação Telegram (T5),
  canal multiusuário e setup (T7 README), agendamento horário (T7 workflow). ✓
- **Sem placeholders:** todo passo tem código real. ✓
- **Consistência de tipos/nomes:** `parse_lotes/fetch_html/LOTES_URL`,
  `format_lote_message/send_telegram`, `load_state/save_state/find_new/main`,
  `STATE_PATH` usados de forma idêntica entre tasks e testes. ✓
