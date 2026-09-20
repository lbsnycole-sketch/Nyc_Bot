# Aviso de Lotes — Lei do Bem (Telegram) 🤖

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
   - **Canal privado:** poste algo no canal e acesse
     `https://api.telegram.org/bot<TOKEN>/getUpdates`, então copie o `chat.id`
     (algo como `-1001234567890`). Alternativa: encaminhe uma mensagem do canal
     para o bot **@userinfobot**.

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
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest -v                 # testes
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=@canal .venv/bin/python check.py
```

## Ajustar a frequência
No arquivo `.github/workflows/check.yml`, mude a linha `cron`. Ex.: `"0 */6 * * *"`
= a cada 6 horas. (Horário em UTC; o cron do GitHub pode atrasar alguns minutos.)
# Nyc_Bot
