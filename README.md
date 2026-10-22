# Plantão de Editais

**De plantão 24h nos concursos de Enfermeiro.**

🔗 **Site:** https://samuelromani.github.io/plantao-de-editais/

O site junta, num lugar só, os concursos com inscrições abertas que têm vaga para Enfermeiro e as provas aplicadas desde 2022, com filtros. Quando aparece um concurso novo nas UFs escolhidas, chega um aviso no Telegram.

Os dados vêm do [PCI Concursos](https://www.pciconcursos.com.br/). O site só lista e linka: os editais e os PDFs das provas continuam hospedados lá.

## O que tem no site

### Concursos abertos
Tabela com órgão, UF, cargos, escolaridade, vagas, salário, período de inscrição, prazo e data em que o concurso apareceu.

- **Filtros:** busca por órgão ou cidade, UF e "Só novos (7 dias)".
- **Ordenação:** clique no cabeçalho da coluna (prazo, salário, vagas, órgão, UF, adicionado).
- **Prazo:** fica âmbar com 7 dias ou menos e vermelho com 2 dias ou menos. Concursos encerrados somem sozinhos.
- **Atualização:** automática a cada 3 horas.

### Provas
1.357 provas de Enfermeiro de 2022 em diante.

- **Filtros:** busca por cargo ou órgão, especialidade (UTI, ESF/PSF, Obstetrícia, Do Trabalho…), banca e ano.
- Cada prova abre a página de download no PCI, onde estão a prova e o gabarito.

Os filtros ficam no endereço da página, então dá para mandar um link já filtrado, por exemplo:
`https://samuelromani.github.io/plantao-de-editais/?uf=RS#concursos`

## Como funciona

```
PCI Concursos ──► GitHub Action (a cada 3h) ──► concursos.json ──► site (GitHub Pages)
                         │
                         └──► concurso novo em Nacional/RS/SC? ──► Telegram + issue no GitHub
```

| Arquivo | Para que serve |
|---|---|
| `index.html` | O site inteiro (HTML, CSS e JavaScript, sem dependências). |
| `concursos.json` | Concursos abertos. Atualizado pela Action; não edite à mão. |
| `provas.json` | Lista de provas. Atualizado rodando `scripts/atualizar_provas.py`. |
| `scripts/atualizar_concursos.py` | Lê a página de vagas de Enfermeiro no PCI, grava `concursos.json` e manda os avisos. |
| `scripts/atualizar_provas.py` | Coleta as provas no PCI banca por banca e grava `provas.json`. |
| `.github/workflows/atualizar-concursos.yml` | Agenda a coleta de concursos, salva as mudanças e dispara os avisos. |

Os scripts usam só a biblioteca padrão do Python (3.10 ou mais novo), sem nada para instalar.

## Avisos no Telegram

Quando surge um concurso novo numa das UFs configuradas, o bot manda uma mensagem com órgão, vagas, salário e prazo, e a Action também abre uma issue no repositório como histórico.

**Configuração (uma vez só):**

1. No Telegram, crie um bot com o [@BotFather](https://t.me/BotFather) (`/newbot`) e guarde o token.
2. Mande qualquer mensagem para o seu bot.
3. Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` e copie o número em `"chat":{"id": ...}`.
4. No GitHub, em **Settings → Secrets and variables → Actions**, crie dois secrets:
   - `TELEGRAM_BOT_TOKEN`: o token do bot
   - `TELEGRAM_CHAT_ID`: o número do chat

**Testar:** aba **Actions → Atualizar concursos → Run workflow**, marcando "Só mandar uma mensagem de teste no Telegram".

**Trocar as UFs do aviso:** edite a linha abaixo em `.github/workflows/atualizar-concursos.yml`. Use `Nacional` para os concursos federais e deixe vazio para receber de todas as UFs.

```yaml
ALERTA_UFS: "Nacional,RS,SC"
```

Só gera aviso o concurso cujo link ainda não estava na lista salva na execução anterior. Prorrogações e mudanças de vagas em concursos já conhecidos atualizam o site, mas não mandam mensagem.

## Atualizar a lista de provas

A lista de provas não muda com frequência, então a atualização é manual:

```bash
python scripts/atualizar_provas.py
```

Leva de 10 a 20 minutos. Depois é só fazer commit e push do `provas.json`. Com `--csv`, o script também gera um `provas.csv` para abrir no Excel.

Para mudar o ano inicial, altere `ANO_INICIAL` no começo do script.

## Rodar o site no computador

O site carrega os arquivos `.json` com `fetch`, então precisa de um servidor local (abrir o `index.html` direto não funciona):

```bash
python -m http.server 8000
```

Depois abra http://localhost:8000.

## Avisos importantes

- Os dados são coletados automaticamente do PCI Concursos e podem conter erros. **Confira sempre o edital oficial** antes de se inscrever.
- Os PDFs das provas ficam atrás de uma verificação de segurança no PCI, por isso o site linka para a página de cada prova em vez de hospedar os arquivos.
- O GitHub desativa Actions agendadas após 60 dias sem atividade no repositório. Como a própria Action faz commits quando a lista muda, na prática ela se mantém ativa. Se parar, reative em **Actions → Atualizar concursos → Enable workflow**.
