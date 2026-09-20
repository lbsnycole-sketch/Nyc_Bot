# Lei do Bem — Notificador de Lotes Novos (Telegram)

**Data:** 2026-09-20
**Autor:** José Guilherme + Claude

## Objetivo

Avisar automaticamente, sem nenhum PC ligado e 100% de graça, sempre que
um **lote novo** for publicado na página de lotes da Lei do Bem do MCTI.
Os avisos são postados num **canal do Telegram** que várias pessoas podem
acompanhar apenas entrando pelo link.

## Fonte monitorada

- Página: `https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/lei-do-bem/paginas/lotes`
- A página tem uma tabela de lotes organizada por ano-base (2024, 2023, …),
  onde cada lote é identificado por número (ex: "14º lote"), tipo (Parecer
  Técnico, Recurso Administrativo, Contestação) e data de publicação, com
  link para o PDF.
- Monitoramos **qualquer lote novo**, sem filtrar por tipo ou ano-base.

## Requisitos e restrições

- **Grátis:** sem serviços pagos, sem cartão de crédito.
- **Sem servidor/PC ligado:** execução agendada em nuvem.
- **Multiusuário:** distribuição via canal do Telegram (sem cadastro de
  inscritos, sem banco de dados).
- **Preciso:** avisar só quando sai lote novo — não qualquer novidade.
- **Frequência:** verificar de hora em hora.

## Arquitetura

Repositório GitHub + **GitHub Actions** com cron horário.

Fluxo a cada execução:
1. Baixar a página de lotes.
2. Extrair a lista de lotes → cada lote vira uma **chave única** (o link do
   PDF é o identificador estável; texto do lote como complemento).
3. Comparar com `state.json` (lotes já vistos na última execução).
4. Para cada lote **novo** (adicionado), postar mensagem no canal do Telegram.
5. Salvar `state.json` atualizado (commit de volta no repositório).

Por que GitHub Actions e não Vercel: cron nativo e generoso no plano grátis
(Vercel Hobby limita cron a ~1x/dia), e o próprio repositório serve de
armazenamento de estado — sem precisar de banco de dados.

## Componentes

- `scraper.py` — baixa a página e devolve a lista de lotes normalizada
  (lista de dicts: `{chave, titulo, url}`). A `chave` é estável (URL do PDF).
- `notifier.py` — envia mensagem ao canal via Telegram Bot API
  (`sendMessage`). Lê `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` do ambiente.
- `check.py` — orquestra: scrape → diff vs `state.json` → notifica novos →
  salva estado.
- `state.json` — memória dos lotes já vistos (versionada no repositório).
- `.github/workflows/check.yml` — cron `0 * * * *`, roda `check.py` e faz
  commit de `state.json` se mudou. Segredos: `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`.
- `README.md` — passo a passo de configuração (BotFather, canal, repo, secrets).

## Detecção de "novo" (diff)

- Estado = conjunto de chaves (URLs dos PDFs) já vistas.
- Novos = chaves presentes agora e ausentes no estado.
- **Só adições geram aviso.** Remoções/ausências nunca geram aviso (protege
  contra página incompleta ou fora do ar).

## Casos especiais / erros

- **Primeira execução (seed):** se `state.json` não existe ou está vazio, a
  rodada apenas **salva** o estado atual, **sem notificar** (evita despejar
  todos os lotes históricos de uma vez).
- **Falha de rede / página incompleta:** se o download falhar ou retornar
  poucos/zero lotes de forma suspeita, o script **não altera o estado e não
  notifica**; tenta de novo na próxima hora. Sai sem erro fatal para não
  gerar e-mails de falha ruidosos.
- **Falha ao enviar no Telegram:** tenta novamente algumas vezes; loga o erro.
  Um lote só é marcado como "visto" depois de notificado com sucesso, para
  não perder avisos.

## Formato da mensagem

```
🆕 Novo lote — Lei do Bem
14º lote do Parecer Técnico – ANO-BASE 2024
📎 <link do PDF>

Fonte: https://www.gov.br/mcti/.../paginas/lotes
```

## Testes

- **Parser:** contra uma cópia salva do HTML da página → extrai o número
  esperado de lotes com chaves/urls corretas.
- **Diff:** estado velho vs lista nova → devolve exatamente os novos.
- **Seed:** primeira execução (estado vazio) não notifica e salva o estado.
- **Notifier:** com HTTP mockado, monta a chamada correta ao Telegram.

## Configuração pelo usuário (documentada no README)

1. Criar bot no **@BotFather** (`/newbot`) → obter `TELEGRAM_BOT_TOKEN`.
2. Criar canal no Telegram, adicionar o bot como **administrador**, obter o
   `@username`/id → `TELEGRAM_CHAT_ID`.
3. Criar repositório GitHub, subir os arquivos, cadastrar os dois segredos em
   **Settings → Secrets and variables → Actions**, habilitar Actions.

## Fora de escopo (YAGNI)

- WhatsApp (oficial exige conta comercial/verificação; não-oficial arrisca ban).
- Cadastro individual de inscritos / comandos do bot.
- Interface web / painel.
- Filtro por tipo ou ano-base (por ora, avisa tudo que é novo).
```

## Stack

Python 3 (`requests` + `beautifulsoup4` para o parser; `pytest` para testes).
