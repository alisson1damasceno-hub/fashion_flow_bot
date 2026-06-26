"""
cliente.py — Nome do cliente + personalização das respostas.

Por quê: o professor quer que as interações sejam PERSONALIZADAS desde o início.
Então, logo no comecinho da conversa, o bot pergunta o nome, GUARDA na sessão
(é a "memória" da Semana 3) e passa a chamar o cliente pelo nome nas respostas.

Aqui ficam 3 coisinhas, bem separadas:
  - primeiro_nome()  -> pega só o 1º nome, bonitinho
  - tratar_nome()    -> cuida de PERGUNTAR e GUARDAR o nome no início
  - personalizar()   -> coloca o nome na frente da resposta do bot
"""
import re

from bot.normalizar import normalizar


def primeiro_nome(nome):
    """Pega só o primeiro nome, com inicial maiúscula. 'maria silva' -> 'Maria'."""
    if not nome:
        return ""
    return nome.strip().split()[0].capitalize()


def _limpar_nome(mensagem):
    """
    Limpa o que o cliente digitou como nome. Tira introduções comuns
    ('meu nome é', 'me chamo', 'sou a/o') e deixa só o nome em si.
    """
    t = mensagem.strip()
    t = re.sub(
        r'(?i)^\s*(meu nome (é|e)|me chamo|pode me chamar de|sou [oa]?|eu sou [oa]?)\s+',
        '', t,
    )
    return t.strip(" .,!?").title()


def tratar_nome(mensagem, sessao):
    """
    Cuida da CAPTURA do nome no começo da conversa.

    Retorna:
      - uma resposta (str) SE ainda estamos tratando do nome (perguntando ou
        confirmando) — nesse caso o fluxo normal do bot NÃO roda neste turno;
      - None se o nome já é conhecido (aí o fluxo normal continua).
    """
    # Já sabemos o nome -> não interfere, segue o fluxo normal do bot.
    if sessao.get("nome_cliente"):
        return None

    # Já perguntamos e estamos esperando -> a mensagem atual É o nome.
    if sessao.get("aguardando_nome"):
        nome = _limpar_nome(mensagem) or "cliente"
        sessao["nome_cliente"] = nome
        sessao["aguardando_nome"] = False
        sessao["ativa"] = True
        return (
            f"Prazer, {primeiro_nome(nome)}! Sou o assistente do setor de produção "
            "da Fashion Flow. Em que posso te ajudar?"
        )

    # Primeira interação da conversa -> pede o nome.
    sessao["aguardando_nome"] = True
    return (
        "Olá! Eu sou o assistente do setor de produção da Fashion Flow. "
        "Antes de começar, como posso te chamar?"
    )


def personalizar(resposta, sessao):
    """
    Coloca o nome do cliente na frente da resposta (ex: 'Maria, ...'), pra deixar
    o atendimento pessoal. Não duplica se a resposta já cita o nome.
    """
    nome = sessao.get("nome_cliente")
    if not nome:
        return resposta
    pn = primeiro_nome(nome)
    # se a resposta já tem o nome (ex: confirmação de pedido), não repete
    if not pn or normalizar(pn) in normalizar(resposta):
        return resposta
    return f"{pn}, {resposta}"
