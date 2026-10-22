"""Coleta as provas de Enfermeiro (2022 em diante) no PCI Concursos e grava provas.json.

A paginação da busca do PCI repete umas provas e pula outras quando há muitos
resultados, então a coleta é feita banca por banca (e, se ainda faltar, banca + ano),
juntando tudo sem duplicar. Demora de 10 a 20 minutos.
"""
import collections
import csv
import datetime
import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ANO_INICIAL = 2022
CARGO = "enfermeiro"
OUT = Path(__file__).resolve().parent.parent / "provas.json"
BASE = "https://www.pciconcursos.com.br/provas/"
UA = {"User-Agent": "Mozilla/5.0"}

ROW_RE = re.compile(
    r'<tr class="lk_link[^"]*" data-url="([^"]+)">\s*'
    r'<td[^>]*><a[^>]*><i[^>]*></i>([^<]*)</a></td>\s*'
    r'<td[^>]*>([^<]*)</td>\s*'
    r'<td[^>]*>(?:<a[^>]*>)?([^<]*)(?:</a>)?</td>\s*'
    r'<td[^>]*>(?:<a href="' + re.escape(BASE) + r'([^"]*)"[^>]*>)?([^<]*)',
    re.S,
)

# Especialidade = primeira regra cujo termo aparece no nome do cargo.
# Termos de até 4 letras precisam ser palavra inteira (ex.: "uti", "esf").
ESPECIALIDADES = [
    ("Do Trabalho", ["trabalho", "trabalhador"]),
    ("Obstetrícia / Saúde da Mulher", ["obstetr", "mulher", "materno", "maternidade", "ginecolog", "perinat"]),
    ("UTI / Terapia Intensiva", ["intensiv", "intesiv", "uti", "coronarian", "centro de tratamento"]),
    ("Urgência e Emergência / SAMU", ["urgencia", "emergenc", "samu", "socorr", "intervencion", "pronto", "upa",
                                       "regulador", "motolancia"]),
    ("ESF / Saúde da Família / Atenção Básica", ["psf", "esf", "familia", "usf", "pacs", "atencao basica",
                                                  "atencao primaria", "ubs", "comunitario"]),
    ("Saúde Mental", ["mental", "caps", "psiquiat"]),
    ("Centro Cirúrgico / CME", ["cirurg", "cme", "esteriliza"]),
    ("Pediatria / Neonatologia", ["pediatr", "neonat", "crianca"]),
    ("Vigilância / Saúde Pública / Fiscal", ["vigilanc", "sanitar", "epidemi", "saude publica", "saude coletiva",
                                              "fiscal"]),
    ("Auditoria / Gestão / Qualidade", ["auditor", "gestao", "gerenc", "qualidade", "nir", "seguranca do paciente"]),
    ("Outras especialidades", ["oncolog", "onco-", "hemato", "hemoter", "nefrolog", "cardio", "hemodin", "perfus",
                               "estoma", "dermat", "transplant", "infec", "scih", "neurolog", "idoso", "indigena",
                               "domiciliar", "sad", "emad", "home", "nutricao", "educacao", "pesquisa", "pedagog",
                               "laborator"]),
    ("Plantonista / Hospitalar", ["plantonista", "hospital"]),
]


def norm(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def especialidade(cargo):
    texto = " " + norm(cargo).replace("(", " ").replace(")", " ").replace("/", " ").replace("-", " - ") + " "
    for nome, termos in ESPECIALIDADES:
        for t in termos:
            if (f" {t} " in texto) if len(t) <= 4 else (t in texto):
                return nome
    return "Enfermeiro (geral)"


def get(url):
    for _ in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) \
                .read().decode("utf-8", "replace")
        except Exception:
            time.sleep(5)
    print("ERRO", url, flush=True)
    return ""


class Coleta:
    def __init__(self, anos):
        self.anos = anos
        self.provas = {}
        self.bancas = set()

    def buscar(self, termo):
        """Percorre todas as páginas da busca; devolve (linhas vistas, links únicos)."""
        vistos, unicos = 0, set()
        for pagina in range(1, 101):
            itens = ROW_RE.findall(get(BASE + termo + ("" if pagina == 1 else f"/{pagina}")))
            if not itens:
                break
            vistos += len(itens)
            for link, cargo, ano, orgao, banca_slug, banca in itens:
                unicos.add(link)
                if banca_slug:
                    self.bancas.add(banca_slug)
                if ano.strip().isdigit() and int(ano) in self.anos:
                    self.provas[link] = [html.unescape(cargo).strip(), ano.strip(),
                                         html.unescape(orgao).strip(), html.unescape(banca).strip(), link]
            if len(itens) < 50:
                break
            time.sleep(0.3)
        return vistos, len(unicos)

    def rodar(self):
        for ano in self.anos:
            self.buscar(f"{CARGO}-{ano}")
        pagina = get("https://www.pciconcursos.com.br/organizadoras/")
        organizadoras = set(re.findall(r'href="https://www\.pciconcursos\.com\.br/organizadoras/([^"/]+)"', pagina))
        fila, feitas = sorted(organizadoras | self.bancas), set()
        while fila:
            banca = fila.pop(0)
            if banca in feitas:
                continue
            feitas.add(banca)
            vistos, unicos = self.buscar(f"{CARGO}-{banca}")
            if unicos < vistos:  # paginação embaralhada: refaz por ano
                for ano in self.anos:
                    v, u = self.buscar(f"{CARGO}-{ano}-{banca}")
                    if u < v:
                        print(f"Aviso: {banca} {ano} pode estar incompleto ({u} de {v}).", flush=True)
            fila += sorted(self.bancas - feitas - set(fila))
        print(f"{len(feitas)} bancas consultadas, {len(self.provas)} provas.", flush=True)
        return list(self.provas.values())


def unificar_bancas(linhas):
    """Junta grafias da mesma banca (Fundatec/FUNDATEC, Instituto AOCP/AOCP) na mais comum."""
    def chave(b):
        k = re.sub(r"[^a-z0-9]", "", norm(b))
        return k[len("instituto"):] if k.startswith("instituto") and len(k) > 12 else k
    grupos = collections.defaultdict(collections.Counter)
    for linha in linhas:
        grupos[chave(linha[3])][linha[3]] += 1
    nome = {k: max(c, key=lambda n: (n.isupper(), c[n], len(n))) for k, c in grupos.items()}
    return [[c, a, o, nome[chave(b)], l] for c, a, o, b, l in linhas]


def main():
    anos = range(ANO_INICIAL, datetime.date.today().year + 1)
    linhas = unificar_bancas(Coleta(anos).rodar())
    linhas.sort(key=lambda r: (-int(r[1]), r[0], r[2]))
    provas = [{"cargo": c, "esp": especialidade(c), "ano": a, "orgao": o, "banca": b, "link": l}
              for c, a, o, b, l in linhas]
    OUT.write_text(json.dumps({"atualizado": datetime.date.today().strftime("%d/%m/%Y"), "provas": provas},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if "--csv" in sys.argv:
        with open(OUT.with_suffix(".csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Cargo", "Especialidade", "Ano", "Órgão", "Banca", "Link"])
            w.writerows([p["cargo"], p["esp"], p["ano"], p["orgao"], p["banca"], p["link"]] for p in provas)
    print(f"{len(provas)} provas gravadas em {OUT.name}.")


if __name__ == "__main__":
    main()
