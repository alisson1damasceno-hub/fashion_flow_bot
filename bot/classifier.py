import re
import unicodedata
from rapidfuzz import fuzz


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def classificar(mensagem, slots, intencoes):
    """
    Recebe a mensagem, os slots extraídos e o DataFrame de intenções.
    Retorna o id da intenção mais provável.
    """
    t = normalizar(mensagem)

    # ── Passo 1: regras por slots (alta prioridade) ──────────────
    # Essas regras têm prioridade porque dependem de slots específicos
    # que as keywords do CSV não conseguem capturar com precisão.

    if slots.get("numero_pedido"):
        return "status_pedido"

    if slots.get("metragem") and slots.get("quantidade"):
        return "consumo_tecido"

    if slots.get("prazo_desejado") and slots.get("quantidade") and slots.get("produto"):
        return "viabilidade_producao"

    if re.search(r'capacidade|materia.?prima|tem (tecido|algodao|dry.?fit|malha)|consegue produzir|da para produzir', t):
        return "viabilidade_producao"

    if re.search(r'alterar|mudar|trocar', t) and re.search(r'tamanho|cor|quantidade', t):
        return "alterar_pedido_especifico"

    if re.search(r'saiu do corte|foi para a costura|esta no corte|esta na costura|meu lote|andamento do pedido|etapa do pedido', t):
        return "status_pedido"

    if slots.get("quantidade") and slots.get("produto"):
        if re.search(r'custa|preco|valor|orcamento|quanto fica', t):
            return "combinado_preco_qtd_produto"
        if re.search(r'prazo|dias|quando|tempo|termina|previsao', t):
            return "combinado_prazo_qtd_produto"

    if slots.get("tecido") and slots.get("personalizacao"):
        return "combinado_personalizacao_em_tecido"

    if slots.get("tecido") and slots.get("produto"):
        return "combinado_tecido_em_produto"

    if slots.get("cor") and slots.get("tecido"):
        return "combinado_cor_em_tecido"

    if slots.get("produto") and slots.get("grade"):
        return "combinado_tamanho_em_produto"

    if slots.get("produto") and slots.get("uso"):
        return "combinado_gramatura_produto_uso"

    # ── Passo 2: keywords exatas do CSV ──────────────────────────
    for _, row in intencoes.iterrows():
        keywords = str(row["palavras_chave"]).strip()
        if not keywords or keywords == "nan":
            continue
        for kw in keywords.split("|"):
            kw = normalizar(kw.strip())
            if kw and kw in t:
                return row["id_intencao"]

    # ── Passo 3: similaridade textual (rapidfuzz) ────────────────
    melhor_score = 0
    melhor_intencao = None

    for _, row in intencoes.iterrows():
        keywords = str(row["palavras_chave"]).strip()
        if not keywords or keywords == "nan":
            continue
        for kw in keywords.split("|"):
            kw = normalizar(kw.strip())
            if not kw:
                continue
            score = fuzz.partial_ratio(kw, t)
            if score > melhor_score:
                melhor_score = score
                melhor_intencao = row["id_intencao"]

    if melhor_score >= 85:
        return melhor_intencao

    # ── Passo 4: fallback ────────────────────────────────────────
    return "fallback"
