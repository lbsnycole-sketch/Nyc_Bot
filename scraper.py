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
