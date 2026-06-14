# Fashion Flow Bot

Chatbot de atendimento de produção têxtil da FashionFlow. Responde dúvidas sobre
preços, prazos, tecidos, personalização, estoque e pedidos, usando arquivos CSV
como base de conhecimento (sem IA externa) — com classificação por intenção,
contexto de conversa e filtro de segurança para dados sensíveis.

## Requisitos

- Python 3.10 ou superior
- pip

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/alisson1damasceno-hub/fashion_flow_bot.git
cd fashion_flow_bot

# 2. (opcional, recomendado) crie um ambiente virtual
python -m venv venv
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

## Como executar

O bot pode rodar de duas formas: pelo **terminal** (para testes rápidos) ou pela
**interface web** (o atendimento que o cliente usaria).

### Opção 1 — Terminal

```bash
python main.py
```

O bot abre no terminal. Digite suas mensagens e veja as respostas. Comandos:
`sair` encerra a conversa, `/contexto` mostra a memória da sessão.

### Opção 2 — Interface Web (HTML)

A interface web precisa do servidor (API) ligado, porque o HTML não responde
sozinho: ele pergunta ao Python via HTTP.

```bash
python -m uvicorn app:app --reload
```

Quando aparecer `Application startup complete`, abra no navegador:

```
http://localhost:8000/
```

O campo **"API"** da página já vem preenchido com `http://localhost:8000`, então
o chat funciona direto. Para parar o servidor, use `Ctrl+C` no terminal.

## Estrutura do projeto

```
fashion_flow_bot/
├── bot/
│   ├── loader.py        # carrega os CSV em memória
│   ├── extractor.py     # extrai dados da mensagem (produto, tecido, cor...)
│   ├── contexto.py      # memória da conversa (herança de slots, foco)
│   ├── classifier.py    # decide a intenção por prioridades
│   ├── seguranca.py     # filtro: bloqueia senha, CVV, número de cartão
│   └── responder.py     # monta a resposta lendo o CSV
├── data/                # base de conhecimento (CSV)
├── main.py              # execução pelo terminal
├── app.py               # API FastAPI + serve o index.html
├── index.html           # interface web
└── requirements.txt
```

## Deploy

O backend é uma API FastAPI e precisa de um servidor que rode Python de forma
persistente. Plataformas recomendadas: **Railway**, **Render** ou
**Hugging Face Spaces** (o `Procfile` já está pronto). O Vercel não é adequado
para este tipo de backend. Ao hospedar, troque a URL no campo "API" da página
pelo endereço público do servidor.
