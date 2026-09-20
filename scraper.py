import re
import requests
from bs4 import BeautifulSoup

LOTES_URL = "https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/lei-do-bem/paginas/lotes"

_LOTE_RE = re.compile(r"\blote\b", re.I)
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_NUM_RE = re.compile(r"(\d+)\s*[º°]\s*lote\b", re.I)
_ANO_RE = re.compile(r"\b(20\d{2})\b")


def fetch_html(url=LOTES_URL, timeout=30):
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (LeiDoBemBot)"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text


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
        m_num = _NUM_RE.search(titulo)
        numero = m_num.group(1) if m_num else None
        m_ano = _ANO_RE.search(titulo)
        ano = m_ano.group(1) if m_ano else None
        lotes.append({
            "titulo": titulo,
            "data": data,
            "url": url,
            "chave": chave,
            "numero": numero,
            "ano": ano,
        })
    return lotes
