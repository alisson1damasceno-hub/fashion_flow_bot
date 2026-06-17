"""
Gerenciamento de contexto da conversa (a "memória do garçom").

Design:
- foco_atual: slots do assunto que está sendo discutido AGORA (curto prazo)
- historico_turnos: registro completo de cada turno (longo prazo, memória)
- aguardando_opcao: menu que o bot mostrou e está aguardando resposta
- ultimo_assunto: última intenção real (ignora "selecao_opcao" de menu)
- ativa: se a conversa já começou
"""
import re
import unicodedata


# ── slots que NUNCA persistem no foco_atual ──────────────────────
# São perguntas de turno único. Saem do foco_atual depois de usados.
SLOTS_EFEMEROS = {"numero_pedido", "metragem", "prazo_desejado", "urgente"}

# ── slots "filhos" de produto ────────────────────────────────────
# Quando o produto muda, esses são invalidados (são propriedades do produto antigo).
SLOTS_FILHOS_PRODUTO = {"personalizacao", "cor", "grade", "tecido"}

# Intenções de orçamento (preço/prazo/viabilidade)
INTENCOES_ORCAMENTO = {
    "combinado_preco_qtd_produto",
    "combinado_prazo_qtd_produto",
    "combinado_prazo_personalizacao_produto",
    "combinado_preco_personalizacao",
    "combinado_desconto_volume",
    "viabilidade_producao",
    "consumo_tecido",
}

# Intenções de pedido específico (status / alterar / cancelar)
INTENCOES_PEDIDO = {
    "status_pedido",
    "alterar_pedido_especifico",
    "alterar_pedido",
    "cancelar_pedido",
}


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def criar_sessao():
    """Cria sessão nova e vazia."""
    return {
        "foco_atual": {},        # slots do assunto atual (curto prazo)
        "historico_turnos": [],  # registro completo de cada turno (longo prazo)
        "aguardando_opcao": None,
        # ── estados do CRUD de pedidos ──────────────────────────────
        "aguardando_id": None,          # ação esperando o ID ("status_pedido"/"cancelar_pedido"/...)
        "alteracao_pendente": None,     # {campo, valor} guardado até o cliente mandar o ID
        "registro_pedido": None,        # dados coletados do pedido em registro (CREATE), ou None
        "registro_campo_pendente": None,  # campo que estamos perguntando agora
        "ultimo_assunto": None,
        "ativa": False,
    }


def resetar_sessao(sessao):
    """Zera tudo (usado em despedida real)."""
    sessao["foco_atual"] = {}
    sessao["historico_turnos"] = []
    sessao["aguardando_opcao"] = None
    sessao["aguardando_id"] = None
    sessao["alteracao_pendente"] = None
    sessao["registro_pedido"] = None
    sessao["registro_campo_pendente"] = None
    sessao["ultimo_assunto"] = None
    sessao["ativa"] = False
    return sessao


def merge_com_contexto(slots_do_turno, sessao):
    """
    Junta os slots do turno atual com os do contexto, aplicando regras de invalidação.

    Princípio: quando o assunto principal muda, slots dependentes são esquecidos
    do FOCO atual — mas continuam preservados no histórico de turnos.

    Retorna: dict de slots EFETIVOS (para o classifier/responder usarem),
    SEM modificar a sessão ainda (isso vira responsabilidade do main/app).
    """
    foco = dict(sessao.get("foco_atual", {}))

    # Regra 1: se o produto mudou no turno atual, esquecer slots-filhos do produto antigo
    produto_novo = slots_do_turno.get("produto")
    if produto_novo and foco.get("produto") and produto_novo != foco["produto"]:
        for k in SLOTS_FILHOS_PRODUTO:
            foco.pop(k, None)

    # Regra 2: aplica slots novos por cima
    for chave, valor in slots_do_turno.items():
        foco[chave] = valor

    return foco


def atualizar_sessao_pos_turno(sessao, mensagem, slots_efetivos, intencao, resposta):
    """
    Persiste mudanças na sessão DEPOIS que o turno foi respondido.

    - Salva no histórico_turnos
    - Atualiza foco_atual (removendo slots efêmeros)
    - Atualiza ultimo_assunto (mas não com 'selecao_opcao')
    """
    # Histórico cresce sempre
    sessao["historico_turnos"].append({
        "msg": mensagem,
        "intencao": intencao,
        "slots": dict(slots_efetivos),
        "resposta": resposta[:200],  # resumo
    })

    # Foco atual: remove slots efêmeros (eles só valem pro turno em que apareceram)
    novo_foco = {k: v for k, v in slots_efetivos.items() if k not in SLOTS_EFEMEROS}

    # Regra: se mudou para intenção de pedido, esquecer produto/qtd de orçamento
    if intencao in INTENCOES_PEDIDO and sessao.get("ultimo_assunto") in INTENCOES_ORCAMENTO:
        novo_foco.pop("produto", None)
        novo_foco.pop("quantidade", None)

    sessao["foco_atual"] = novo_foco

    # ultimo_assunto: ignora seleções de menu (preserva o assunto real anterior)
    if intencao != "selecao_opcao":
        sessao["ultimo_assunto"] = intencao

    sessao["ativa"] = True
    return sessao


# ───────────────────────── despedida e casual ─────────────────────────

# Despedidas PURAS (sem agradecimento — agradecimento é casual)
_DESPEDIDAS_EXATAS = {
    "tchau", "ate logo", "ate mais", "flw", "vlw", "falou",
    "era so isso", "resolvido", "encerrar", "finalizar",
    "ate a proxima", "ate depois", "ate amanha",
}

# Casuais — agradecimentos curtos e confirmações
_CASUAIS = {
    "blz", "beleza", "ok", "certo", "entendi", "sim", "nao", "legal",
    "otimo", "perfeito", "ta", "massa", "show", "top",
    "obrigado", "obrigada", "obg", "valeu", "brigado", "brigada",
    "tmj", "tranquilo",
}


def is_despedida(mensagem):
    """
    Verdadeiro APENAS se a mensagem é uma despedida pura, curta e isolada.

    Conserta o Crítico 4: antes "obrigado, e me fala o prazo" resetava a
    sessão por causa do substring match. Agora exige que a mensagem inteira
    seja despedida (≤ 3 palavras E todas as palavras estão na lista).
    """
    t = normalizar(mensagem).strip()
    if not t:
        return False
    # match exato (qualquer comprimento)
    if t in _DESPEDIDAS_EXATAS:
        return True
    # mensagem curta (≤ 3 palavras) cujas palavras são todas despedidas
    palavras = re.findall(r"\w+", t)
    if 1 <= len(palavras) <= 3:
        # cada palavra é despedida ou casual (ex: "ok tchau", "valeu flw")
        if all(p in _DESPEDIDAS_EXATAS or p in _CASUAIS for p in palavras):
            # mas exige pelo menos UMA palavra de despedida pura
            if any(p in _DESPEDIDAS_EXATAS or p in {"tchau", "flw", "falou"} for p in palavras):
                return any(p in _DESPEDIDAS_EXATAS or p == "flw" or p == "tchau" or p == "falou"
                           for p in palavras)
    return False


def is_casual(mensagem):
    """
    Verdadeiro se a mensagem é só uma confirmação/agradecimento curto.

    Usada pra dizer "pode continuar" sem reiniciar o assunto.
    """
    t = normalizar(mensagem).strip()
    if not t:
        return False
    # match exato
    if t in _CASUAIS:
        return True
    # 2-3 palavras todas casuais (ex: "valeu, obg")
    palavras = re.findall(r"\w+", t)
    if 1 <= len(palavras) <= 3 and all(p in _CASUAIS for p in palavras):
        return True
    return False
