def criar_sessao():
    """
    Cria uma sessão nova e vazia.
    Chamada no início de cada conversa.
    """
    return {
        "slots_acumulados": {},   # slots já extraídos ao longo da conversa
        "aguardando_opcao": None, # nome do menu ativo, se houver
        "ultimo_assunto": None,   # última intenção respondida
        "ativa": False            # False = conversa ainda não iniciada
    }


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