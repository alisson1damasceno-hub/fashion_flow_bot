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
from rapidfuzz import fuzz

from bot.normalizar import normalizar
# Palavras que abortam o registro de pedido (usadas aqui pra decidir se uma
# mensagem durante o registro é "abandonar o formulário" antes de recalcular
# a intenção — ver bloco 0b). Fonte da verdade: bot/responder.py.
from bot.responder import ABORTAR_REGISTRO


def _parece_resposta_de_campo(pendente, mensagem, slots_turno):
    """
    Palpite rápido e barato: essa mensagem parece só a resposta do campo que
    o formulário de registro está esperando agora (ex: "M", "42", "nenhuma")?

    Isso evita rodar o Sistema de Pesos (pensado pra frases inteiras) em cima
    de respostas curtas — que podem bater por acidente com uma palavra-chave
    de outro assunto (ex: fuzzy matching dando score alto pra uma letra só) e
    gerar um falso positivo de "mudança de assunto".
    """
    if not pendente:
        return False
    # O extractor já reconheceu o valor certinho pra este campo — sem dúvida.
    if slots_turno.get(pendente):
        return True
    t = normalizar(mensagem).strip()
    if pendente == "quantidade":
        return bool(re.match(r'^\d+$', t))
    if pendente == "tamanho":
        return t in {"pp", "p", "m", "g", "gg", "xgg", "infantil", "plus size", "plus_size"}
    if pendente == "personalizacao":
        return t in {"nenhuma", "nenhum", "sem personalizacao", "sem personalização"}
    return False


def _peso(row):
    """
    Lê o PESO da intenção (coluna 'peso' do intencoes.csv). É o número que
    decide quem ganha quando mais de uma intenção bate na mesma frase:
    quanto maior o peso, mais a intenção tem prioridade. Se faltar, usa 5.
    """
    try:
        p = float(row.get("peso", 5))
        return p if p == p else 5.0   # p == p é False quando é NaN
    except (TypeError, ValueError):
        return 5.0


def classificar(mensagem, slots_turno, slots_efetivos, intencoes, sessao=None):
    """
    Retorna o id da intenção classificada.
    """
    t = normalizar(mensagem)

    # ── 0. Aguardando opção de menu ──────────────────────────────
    if sessao and sessao.get("aguardando_opcao"):
        return "selecao_opcao"

    # ── 0b. Fluxos de CRUD de pedido em andamento ────────────────
    if sessao:
        # Registro de pedido (CREATE) em andamento.
        if sessao.get("registro_pedido") is not None:
            # Palavra de abortar formulário ("cancelar", "esquece"...) tem
            # prioridade — é o responder.py quem trata o texto de cancelamento.
            if t.strip() in ABORTAR_REGISTRO:
                return "registrar_pedido"

            # Resposta curta e esperada do campo atual (ex: "M", "42",
            # "nenhuma", ou o extractor já reconheceu o valor) → nem precisa
            # recalcular, é claramente continuação do formulário.
            pendente = sessao.get("registro_campo_pendente")
            if _parece_resposta_de_campo(pendente, mensagem, slots_turno):
                return "registrar_pedido"

            # RECÁLCULO DE INTENÇÃO ("o ataque da mudança de assunto"): antes,
            # aqui a gente simplesmente devolvia "registrar_pedido" pra
            # QUALQUER mensagem, e o cliente ficava preso no formulário pra
            # sempre se mudasse de assunto no meio do caminho. Agora, a cada
            # mensagem nova, recalculamos a intenção de verdade usando o
            # Sistema de Pesos (as mesmas regras dos passos 1 a 9 abaixo).
            nova_intencao = _classificar_pelas_regras(
                t, mensagem, slots_turno, slots_efetivos, intencoes, sessao
            )

            # Se a mensagem não bateu com nenhum outro assunto (fallback),
            # é porque ela é só uma resposta de campo do formulário mesmo
            # (ex: "M", "42", "nenhuma") → segue coletando normalmente.
            if nova_intencao in ("fallback", "registrar_pedido"):
                return "registrar_pedido"

            # Intenção diferente e reconhecida com confiança → o cliente
            # mudou de assunto. Abandona o formulário e devolve a nova
            # intenção pro Roteador Central (app.py) decidir o que fazer —
            # em vez de forçar o fluxo de registro pra sempre.
            return nova_intencao

        # Pedimos um ID antes e ele chegou agora → executa a ação que ficou pendente
        # (consultar / cancelar / alterar). Guardada em sessao["aguardando_id"].
        acao_pendente = sessao.get("aguardando_id")
        if acao_pendente and slots_turno.get("numero_pedido"):
            return acao_pendente

    return _classificar_pelas_regras(t, mensagem, slots_turno, slots_efetivos, intencoes, sessao)


def _classificar_pelas_regras(t, mensagem, slots_turno, slots_efetivos, intencoes, sessao=None):
    """
    O "Sistema de Pesos": passos 1 a 9. Isolado numa função própria pra poder
    ser chamado tanto no caminho normal quanto para RECALCULAR a intenção
    durante um fluxo em andamento (ex: registro de pedido — ver bloco 0b).
    """
    # ── 1. Regras por VERBO (alta prioridade — vencem regras por slot) ──
    # CRÍTICO 6: "cancelar" vem antes de "numero_pedido vira status"
    if re.search(r'\bcancelar\b|\bcancelamento\b', t):
        return "cancelar_pedido"

    if re.search(r'\balterar\b|\bmudar\b|\btrocar\b', t) and re.search(
        r'tamanho|cor|quantidade|pedido', t
    ):
        return "alterar_pedido_especifico"

    # CREATE: iniciar o registro de um pedido novo
    # ("quero fazer um pedido", "registrar pedido", "novo pedido"...)
    if re.search(r'\b(registrar|cadastrar|abrir|criar)\b.*\bpedido\b', t) or \
       re.search(r'\b(fazer|faz)\b.*\bpedido\b', t) or \
       re.search(r'\bnovo pedido\b', t):
        return "registrar_pedido"

    # Obs: "avançar etapa" NÃO é ação do cliente (é da produção interna), então
    # não tem regra de chat aqui. A função existe em bot/pedidos/atualizar.py e é
    # exercitada pelos testes e pela demo, mas o cliente não dispara isso conversando.

    # CRÍTICO 5: estoque vence pedido herdado
    if re.search(r'\bestoque\b|\bem estoque\b|\btem (algodao|dry.?fit|malha|jeans|viscose|linho|moletom|suplex|tecido|tencel|alfaiataria|la|rpet)\b', t):
        return "disponibilidade_materiais"

    # READ: consultar/acompanhar o andamento de um pedido (pede o ID depois).
    # Precisa vir aqui em cima pra "status do pedido" não cair no menu genérico
    # etapas_pedido (que casa pela mesma palavra-chave lá embaixo).
    if re.search(r'status d[oae]s? (meu )?pedido|consultar (o )?(meu )?pedido|'
                 r'acompanhar (o )?(meu )?pedido|onde esta (o )?meu pedido|'
                 r'andamento d[oae] (meu )?pedido|fase d[oae] (meu )?pedido|'
                 r'etapa d[oae] (meu )?pedido|saiu do corte|foi para a costura|'
                 r'esta no corte|esta na costura|meu lote', t):
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

    # ── 8. Palavras-chave do CSV (desempate por PESO) ─────────────
    # Antes era "a primeira intenção que bater vence". Agora coletamos TODAS as
    # intenções cuja palavra-chave aparece na frase e ficamos com a de MAIOR PESO.
    melhor_peso = -1.0
    melhor_kw = None
    for _, row in intencoes.iterrows():
        keywords = str(row["palavras_chave"]).strip()
        if not keywords or keywords == "nan":
            continue
        for kw in keywords.split("|"):
            kw = normalizar(kw.strip())
            if kw and kw in t:
                peso = _peso(row)
                if peso > melhor_peso:
                    melhor_peso = peso
                    melhor_kw = row["id_intencao"]
                break  # essa intenção já bateu; não precisa testar as outras kw dela
    if melhor_kw:
        return melhor_kw

    # ── 9. Similaridade textual (rapidfuzz), desempate por peso ───
    melhor_score = 0
    melhor_peso = -1.0
    melhor_intencao = None
    for _, row in intencoes.iterrows():
        keywords = str(row["palavras_chave"]).strip()
        if not keywords or keywords == "nan":
            continue
        peso = _peso(row)
        for kw in keywords.split("|"):
            kw = normalizar(kw.strip())
            if not kw:
                continue
            score = fuzz.partial_ratio(kw, t)
            # vence o maior score; se empatar no score, vence o maior peso
            if score > melhor_score or (score == melhor_score and peso > melhor_peso):
                melhor_score = score
                melhor_peso = peso
                melhor_intencao = row["id_intencao"]

    if melhor_score >= 85:
        return melhor_intencao

    return "fallback"
