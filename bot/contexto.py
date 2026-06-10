def criar_sessao():
    """
    Cria uma sessão nova e vazia.
    Chamada no início de cada conversa.
    """
    return {
        "slots_acumulados": {},    # slots já extraídos ao longo da conversa
        "aguardando_opcao": None,  # nome do menu ativo, se houver
        "ultimo_assunto": None,    # última intenção respondida
        "ativa": False,            # False = conversa ainda não iniciada
        "historico_intencoes": [], # todas as intenções detectadas na conversa
    }


def registrar_intencao(sessao, intencao):
    """
    Adiciona a intenção ao histórico se ainda não estiver lá.
    Intenções de sistema (fallback, selecao_opcao) são ignoradas.
    """
    ignorar = {"fallback", "selecao_opcao"}
    if intencao not in ignorar and intencao not in sessao["historico_intencoes"]:
        sessao["historico_intencoes"].append(intencao)


def intencoes_relacionadas(historico):
    """
    Dado o histórico de intenções da conversa, retorna quais
    áreas temáticas já foram abordadas.
    Usado para desambiguar mensagens vagas.
    """
    areas = set()
    mapeamento = {
        "combinado_prazo_qtd_produto":        "prazo",
        "combinado_preco_qtd_produto":        "preco",
        "viabilidade_producao":               "producao",
        "consumo_tecido":                     "producao",
        "combinado_personalizacao_em_tecido": "personalizacao",
        "combinado_tecido_em_produto":        "tecido",
        "combinado_cor_em_tecido":            "tecido",
        "combinado_gramatura_produto_uso":    "tecido",
        "combinado_tamanho_em_produto":       "tamanho",
        "status_pedido":                      "pedido",
        "alterar_pedido_especifico":          "pedido",
    }
    for intencao in historico:
        area = mapeamento.get(intencao)
        if area:
            areas.add(area)
    return areas


def merge_slots(sessao, slots_novos):
    """
    Mescla os slots novos com os que já estão na sessão.
    Slots novos têm prioridade — sobrescrevem os antigos
    quando o usuário muda de assunto.
    Slots ausentes na mensagem nova são herdados da sessão.
    """
    for chave, valor in slots_novos.items():
        sessao["slots_acumulados"][chave] = valor
    return sessao["slots_acumulados"]


def resetar_sessao(sessao):
    """
    Limpa a sessão quando o usuário se despede.
    """
    sessao["slots_acumulados"] = {}
    sessao["aguardando_opcao"] = None
    sessao["ultimo_assunto"] = None
    sessao["ativa"] = False
    sessao["historico_intencoes"] = []
    return sessao


def is_despedida(mensagem):
    """
    Detecta se o usuário quer encerrar a conversa.
    """
    import unicodedata
    t = mensagem.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    palavras = ["tchau", "ate logo", "ate mais", "encerrar", "finalizar", "obrigado", "obrigada", "valeu", "flw"]
    return any(p in t for p in palavras)


def is_casual(mensagem):
    """
    Detecta mensagens casuais que não devem reiniciar a conversa.
    """
    import unicodedata
    t = mensagem.lower().strip()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    palavras = ["blz", "beleza", "ok", "certo", "entendi", "sim", "nao", "legal", "otimo", "perfeito", "certo", "ta", "massa", "show", "top", "valeu", "obg", "tmj"]
    return t in palavras