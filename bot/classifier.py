import re
import unicodedata
from rapidfuzz import fuzz


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def classificar(mensagem, slots, intencoes, sessao=None):
    """
    Recebe a mensagem, os slots extraídos e o DataFrame de intenções.
    Retorna o id da intenção mais provável.
    """
    t = normalizar(mensagem)

    # se o bot está aguardando uma escolha de menu, processa como seleção
    if sessao and sessao.get("aguardando_opcao"):
        return "selecao_opcao"

    # herda intenção anterior se usuário trouxe quantidade nova explícita
    import re as _re
    if sessao and sessao.get("ultimo_assunto") in (
        "combinado_prazo_qtd_produto", "combinado_preco_qtd_produto", "viabilidade_producao"
    ):
        slots_merged = {**sessao.get("slots_acumulados", {}), **slots}
        if slots_merged.get("quantidade") and slots_merged.get("produto"):
            if _re.search(r'\d+', mensagem):
                return sessao["ultimo_assunto"]

    # número solto sem menu ativo — ignora
    if re.match(r'^\d+$', mensagem.strip()):
        if not (sessao and sessao.get("aguardando_opcao")):
            if not (sessao and sessao.get("ultimo_assunto") in (
                "combinado_prazo_qtd_produto", "combinado_preco_qtd_produto", "viabilidade_producao"
            )):
                return "fallback"

    # ── Passo 1: regras por slots (alta prioridade) ──────────────

    if slots.get("numero_pedido"):
        return "status_pedido"

    if slots.get("metragem") and slots.get("quantidade"):
        return "consumo_tecido"

    # intenção explícita na frase tem prioridade sobre slots
    if slots.get("quantidade") and slots.get("produto"):
        if re.search(r'custa|preco|valor|orcamento|quanto fica', t):
            return "combinado_preco_qtd_produto"
        if re.search(r'prazo|dias|quando|tempo|termina|previsao', t):
            return "combinado_prazo_qtd_produto"

    # só cai em viabilidade se não havia intenção de prazo/preço explícita
    if slots.get("prazo_desejado") and slots.get("quantidade") and slots.get("produto"):
        return "viabilidade_producao"

    if re.search(r'capacidade|materia.?prima|tem (tecido|algodao|dry.?fit|malha)|consegue produzir|da para produzir', t):
        return "viabilidade_producao"

    if re.search(r'alterar|mudar|trocar', t) and re.search(r'tamanho|cor|quantidade', t):
        return "alterar_pedido_especifico"

    if re.search(r'saiu do corte|foi para a costura|esta no corte|esta na costura|meu lote|andamento do pedido|etapa do pedido', t):
        return "status_pedido"

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

    # ── Passo 4: fallback por contexto (histórico de intenções) ──
    # Se a mensagem é vaga mas já há áreas discutidas na conversa,
    # tenta encontrar uma intenção compatível com o histórico.
    if sessao:
        from bot.contexto import intencoes_relacionadas
        historico = sessao.get("historico_intencoes", [])
        areas_ativas = intencoes_relacionadas(historico)

        # palavras vagas que indicam continuidade de assunto
        if areas_ativas and re.search(r'\b(prazo|tempo|dias|quando|entrega|demora)\b', t):
            if "prazo" in areas_ativas or "producao" in areas_ativas:
                return "combinado_prazo_qtd_produto"

        if areas_ativas and re.search(r'\b(preco|valor|custo|quanto|orcamento|custa)\b', t):
            if "preco" in areas_ativas:
                return "combinado_preco_qtd_produto"

        if areas_ativas and re.search(r'\b(tecido|material|malha|algodao|dry)\b', t):
            if "tecido" in areas_ativas:
                # retorna a última intenção de tecido do histórico
                for intencao_hist in reversed(historico):
                    if intencao_hist in (
                        "combinado_tecido_em_produto",
                        "combinado_cor_em_tecido",
                        "combinado_personalizacao_em_tecido",
                        "combinado_gramatura_produto_uso",
                    ):
                        return intencao_hist

        if areas_ativas and re.search(r'\b(pedido|status|etapa|situacao)\b', t):
            if "pedido" in areas_ativas:
                return "status_pedido"

    # ── Passo 5: fallback ────────────────────────────────────────
    return "fallback"
