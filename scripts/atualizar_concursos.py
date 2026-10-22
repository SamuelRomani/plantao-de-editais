"""Coleta os concursos com inscrições abertas para Enfermeiro no PCI Concursos
e grava concursos.json, preservando a data em que cada concurso apareceu."""
import datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://www.pciconcursos.com.br/vagas/enfermeiro"
OUT = Path(__file__).resolve().parent.parent / "concursos.json"
ALERTA = Path(__file__).resolve().parent.parent / "alerta.md"
SITE = "https://samuelromani.github.io/plantao-de-editais/#concursos"
TZ = datetime.timezone(datetime.timedelta(hours=-3))

# "na" = aberto, "da" = aberto em destaque, "ea" = encerrado (ignorado)
ITEM_RE = re.compile(
    r'<div class="(na|da)"[^>]*data-url="([^"]+)".*?'
    r'<div class="ca"><a[^>]*>([^<]*)</a>.*?'
    r'<div class="cc">(.*?)</div>.*?'
    r'<div class="cd">(.*?)</div>\s*<div class="ce">(.*?)</div>',
    re.S,
)


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def fim_inscricoes(periodo):
    """Última data dd/mm/aaaa do texto (ex.: '27/11 a 28/12/2026' -> 2026-12-28)."""
    datas = re.findall(r"(\d{2})/(\d{2})/(\d{4})", periodo)
    if not datas:
        return ""
    d, m, a = datas[-1]
    return f"{a}-{m}-{d}"


def coletar():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    pagina = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    concursos = []
    for classe, link, orgao, uf, detalhes, periodo in ITEM_RE.findall(pagina):
        partes = [text(p) for p in re.split(r"<br\s*/?>", detalhes)]
        partes += [""] * (3 - len(partes))
        concursos.append({
            "orgao": text(orgao),
            "uf": text(uf) or "Nacional",
            "vagas": partes[0],
            "cargos": partes[1],
            "escolaridade": partes[2],
            "inscricoes": text(periodo),
            "fim": fim_inscricoes(text(periodo)),
            "destaque": classe == "da",
            "link": link,
        })
    return concursos


def main():
    concursos = coletar()
    if not concursos:
        sys.exit("Nenhum concurso encontrado: a página do PCI pode ter mudado.")

    hoje = datetime.datetime.now(TZ).date().isoformat()
    anteriores, inicio = {}, hoje
    if OUT.exists():
        antigo = json.loads(OUT.read_text(encoding="utf-8"))
        anteriores = {c["link"]: c for c in antigo["concursos"]}
        inicio = antigo.get("inicio", hoje)

    for c in concursos:
        c["desde"] = anteriores.get(c["link"], {}).get("desde", hoje)

    if [dict(c) for c in concursos] == list(anteriores.values()):
        print("Sem mudanças.")
        return

    OUT.write_text(json.dumps(
        # "inicio" = primeira coleta; o site só marca como novo o que surgiu depois dela
        {"atualizado": datetime.datetime.now(TZ).strftime("%d/%m/%Y %H:%M"), "inicio": inicio,
         "concursos": concursos},
        ensure_ascii=False, indent=1), encoding="utf-8")
    novos = [c for c in concursos if c["link"] not in anteriores]
    print(f"{len(concursos)} concursos abertos, {len(novos)} novos.")
    if anteriores:
        escrever_alerta(novos)


def escrever_alerta(novos):
    """Grava alerta.md com os novos concursos das UFs em ALERTA_UFS (ex.: 'Nacional,RS,SC')."""
    ufs = ufs_alerta()
    alvo = [c for c in novos if not ufs or c["uf"] in ufs]
    if not alvo:
        return
    linhas = [f"- **[{c['orgao']}]({c['link']})** ({c['uf']}): {c['vagas']}. Inscrições: {c['inscricoes']}"
              for c in alvo]
    ALERTA.write_text("\n".join(linhas) + f"\n\nVer todos no site: {SITE}\n", encoding="utf-8")
    print(f"Alerta: {len(alvo)} novo(s) em {', '.join(sorted(ufs)) or 'todas as UFs'}.")
    enviar_telegram(alvo, "🚨 <b>Plantão de Editais</b>\nNovo concurso de Enfermeiro na área:")


def ufs_alerta():
    return {u.strip() for u in os.environ.get("ALERTA_UFS", "").split(",") if u.strip()}


def enviar_telegram(concursos, titulo):
    """Envia a lista pelo bot, se TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID estiverem definidos."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip().removeprefix("bot")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip().strip('"')
    if not (token and chat):
        print("Telegram não configurado; pulando.")
        return
    e = html.escape
    blocos = [f'<a href="{e(c["link"])}"><b>{e(c["orgao"])}</b></a> ({e(c["uf"])})\n'
              f'{e(c["vagas"])}\nInscrições: {e(c["inscricoes"])}' for c in concursos]
    # o Telegram limita cada mensagem a 4096 caracteres
    mensagens, atual = [], titulo
    for b in blocos + [f'<a href="{SITE}">Ver todos no site</a>']:
        if len(atual) + len(b) + 2 > 4000:
            mensagens.append(atual)
            atual = ""
        atual += "\n\n" + b
    mensagens.append(atual)
    for texto in mensagens:
        dados = urllib.parse.urlencode({"chat_id": chat, "text": texto.strip(), "parse_mode": "HTML",
                                        "disable_web_page_preview": "true"}).encode()
        try:
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", dados, timeout=30)
        except urllib.error.HTTPError as erro:
            motivo = erro.read().decode("utf-8", "replace")
            dica = {400: "confira o TELEGRAM_CHAT_ID e se você já mandou uma mensagem para o bot",
                    401: "o TELEGRAM_BOT_TOKEN está errado", 404: "o TELEGRAM_BOT_TOKEN está errado",
                    403: "o bot foi bloqueado ou não pode falar nesse chat"}.get(erro.code, "")
            sys.exit(f"Telegram recusou a mensagem ({erro.code}): {motivo}\nDica: {dica}")
    print(f"Telegram: {len(mensagens)} mensagem(ns) enviada(s).")


def testar_telegram():
    """Manda os 3 concursos abertos mais recentes do filtro, só para conferir se o bot funciona."""
    ufs = ufs_alerta()
    todos = json.loads(OUT.read_text(encoding="utf-8"))["concursos"]
    alvo = [c for c in todos if not ufs or c["uf"] in ufs][:3]
    enviar_telegram(alvo, "✅ <b>Plantão de Editais</b>\nTeste do aviso. Exemplos do seu filtro:")


if __name__ == "__main__":
    testar_telegram() if "--testar-telegram" in sys.argv else main()
