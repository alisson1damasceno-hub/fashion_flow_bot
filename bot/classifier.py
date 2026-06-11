"""
Classificação de intenção a partir da mensagem + slots + contexto.

Recebe DOIS dicionários de slots:
- slots_turno:    o que o usuário disse AGORA (sem herança de contexto)
- slots_efetivos: foco_atual + slots_turno (com herança)

A separação evita bugs onde uma regra dispara só porque um slot herdado
ainda está na sessão (ex: CRÍTICO 5 — numero_pedido fazendo qualquer
mensagem virar status_pedido).
"""
import re
import unicodedata
from rapidfuzz import fuzz


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def classificar(mensagem, slots_turno, slots_efetivos, intencoes, sessao=None):
    """
    Retorna o id da intenção classificada.
    """
    t = normalizar(mensagem)

    # ── 0. Aguardando opção de menu ──────────────────────────────
    if sessao and sessao.get("aguardando_opcao"):
        return "selecao_opcao"

    # ── 1. Regras por VERBO (alta prioridade — vencem regras por slot) ──
    # CRÍTICO 6: "cancelar" vem antes de "numero_pedido vira status"
    if re.search(r'\bcancelar\b|\bcancelamento\b', t):
        return "cancelar_pedido"

    if re.search(r'\balterar\b|\bmudar\b|\btrocar\b', t) and re.search(
        r'tamanho|cor|quantidade|pedido', t
    ):
        return "alterar_pedido_especifico"

    # CRÍTICO 5: estoque vence pedido herdado
    if re.search(r'\bestoque\b|\bem estoque\b|\btem (algodao|dry.?fit|malha|jeans|viscose|linho|moletom|suplex|tecido|tencel|alfaiataria|la|rpet)\b', t):
        return "disponibilidade_materiais"

    if re.search(r'saiu do corte|foi para a costura|esta no corte|esta na costura|'
                 r'meu lote|andamento do pedido|etapa do pedido', t):
        return "status_pedido"

    # ── 2. Regras por slot DO TURNO ATUAL ─────────────────────────
    # CRÍTICO 5: numero_pedido só dispara se foi mencionado AGORA,
    # não se está só herdado da sessão.
    if slots_turno.get("numero_pedido"):
        # combinação verbo + numero
        if re.search(r'consultar|status|etapa|onde esta|andamento', t):
            return "status_pedido"
        return "status_pedido"

    # consumo de tecido pede produto + metragem + quantidade
    if slots_turno.get("metragem") and slots_efetivos.get("quantidade") and slots_efetivos.get("produto"):
        return "consumo_tecido"

    # ── 3. Intenções compostas (preço/prazo) ─────────────────────
    quantidade = slots_efetivos.get("quantidade")
    produto = slots_efetivos.get("produto")
    prazo_desejado = slots_efetivos.get("prazo_desejado") or slots_turno.get("prazo_desejado")

    # Intenção EXPLÍCITA na frase tem prioridade
    if quantidade and produto:
        if re.search(r'custa|preco|preço|valor|orcamento|quanto fica|sai por', t):
            return "combinado_preco_qtd_produto"
        if re.search(r'prazo|dias|quando|tempo|termina|previsao|fica pronto', t):
            return "combinado_prazo_qtd_produto"

    # ── 4. Viabilidade de produção ────────────────────────────────
    # ALTO 11: viabilidade vence qtd_grande_volume
    if (prazo_desejado or re.search(r'consigo|da pra|conseguimos|viavel|viável', t)) \
       and quantidade:
        return "viabilidade_producao"

    if re.search(r'capacidade|materia.?prima|consegue produzir|da para produzir', t):
        return "viabilidade_producao"

    # ── 5. Follow-up: usuário refinou um slot, herda último assunto ─
    # ALTO 9: se mensagem traz só um slot novo (personalizacao/tecido/cor)
    # e o último assunto era preço/prazo/viabilidade, herda o assunto.
    ULTIMO_ORCAMENTO = {
        "combinado_preco_qtd_produto",
        "combinado_prazo_qtd_produto",
        "viabilidade_producao",
    }
    if sessao and sessao.get("ultimo_assunto") in ULTIMO_ORCAMENTO:
        slots_novos_chaves = set(slots_turno.keys()) - {"quantidade", "produto"}
        # se a mensagem só adicionou refinamento (sem mudar produto/qtd),
        # e ainda temos qtd+produto no foco, herda o assunto
        if slots_novos_chaves and quantidade and produto:
            return sessao["ultimo_assunto"]

    # ── 6. Combinações por slot ───────────────────────────────────
    if slots_efetivos.get("tecido") and slots_efetivos.get("personalizacao") \
       and (slots_turno.get("tecido") or slots_turno.get("personalizacao")):
        return "combinado_personalizacao_em_tecido"

    if slots_efetivos.get("tecido") and produto \
       and (slots_turno.get("tecido") or slots_turno.get("produto")):
        return "combinado_tecido_em_produto"

    if slots_efetivos.get("cor") and slots_efetivos.get("tecido") \
       and (slots_turno.get("cor") or slots_turno.get("tecido")):
        return "combinado_cor_em_tecido"

    if produto and slots_efetivos.get("grade") and slots_turno.get("grade"):
        return "combinado_tamanho_em_produto"

    if produto and slots_efetivos.get("uso") and slots_turno.get("uso"):
        return "combinado_gramatura_produto_uso"

    # ── 7. Número solto sem contexto → fallback ───────────────────
    if re.match(r'^\d+$', mensagem.strip()):
        return "fallback"

    # Só prazo_desejado sem produto/quantidade — pergunta clarificadora
    # (cenário 12: "preciso em 100 dias" sem mais nada)
    if slots_turno.get("prazo_desejado") and not produto and not quantidade:
        return "prazo_sem_contexto"

    # ── 8. Keywords exatas do CSV ─────────────────────────────────
    for _, row in intencoes.iterrows():
        keywords = str(row["palavras_chave"]).strip()
        if not keywords or keywords == "nan":
            continue
        for kw in keywords.split("|"):
            kw = normalizar(kw.strip())
            if kw and kw in t:
                return row["id_intencao"]

    # ── 9. Similaridade textual (rapidfuzz) ───────────────────────
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

    return "fallback"
