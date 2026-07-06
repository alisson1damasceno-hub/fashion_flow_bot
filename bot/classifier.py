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
        # Registro de pedido (CREATE) em andamento → continua coletando os campos.
        if sessao.get("registro_pedido") is not None:
            return "registrar_pedido"
        # Pedimos um ID antes e ele chegou agora → executa a ação que ficou pendente
        # (consultar / cancelar / alterar). Guardada em sessao["aguardando_id"].
        acao_pendente = sessao.get("aguardando_id")
        if acao_pendente and slots_turno.get("numero_pedido"):
            return acao_pendente

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

    # ── 3b. Prazo COM personalização ──────────────────────────────
    # "prazo com bordado/silk/dtf" caía em personalizacao_X (a DESCRIÇÃO da técnica)
    # em vez de responder o PRAZO. Se a frase fala de prazo E há uma personalização,
    # é pergunta de prazo-com-personalização (com produto/qtd → a versão combinada).
    tem_prazo = bool(re.search(r'\bprazo\b|quanto tempo|demora|quando fica', t))
    pers = slots_efetivos.get("personalizacao")
    if tem_prazo and pers and pers != "nenhuma":
        if produto or quantidade:
            return "combinado_prazo_personalizacao_produto"
        return "prazo_com_personalizacao"

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

    # "capacidade" sozinha NÃO é viabilidade: "capacidade produtiva/da fábrica" é
    # pergunta INFORMATIVA (cai em producao_capacidade na etapa de keyword). Só
    # forçamos viabilidade quando a pessoa pergunta se CONSEGUIMOS produzir algo.
    if re.search(r'consegue(m)? produzir|da p(?:a?ra) produzir|'
                 r'capacidade tecnica|capacidade de produc', t):
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
    # Só tratamos como pergunta de COMPATIBILIDADE/DISPONIBILIDADE se a frase
    # tiver um sinal disso ("combina", "posso usar", "dá pra", "tem em"...).
    # Senão, citar um tecido/cor junto de um produto é INFORMATIVO (não um
    # veredito) — aí deixamos cair no catálogo/tecidos, que faz mais sentido.
    sinal_compat = bool(re.search(
        r'combina|casa com|harmoniza|da pra|posso |pode (usar|fazer|ser)|'
        r'fica bo|serve|aceita|recomend|ideal|funciona|\be bom\b|vale a pena|'
        r'adequad|compat|melhor tecido|qual tecido|\btem\b|disponiv|estoque', t
    ))

    if slots_efetivos.get("tecido") and slots_efetivos.get("personalizacao") \
       and (slots_turno.get("tecido") or slots_turno.get("personalizacao")) \
       and sinal_compat:
        return "combinado_personalizacao_em_tecido"

    if slots_efetivos.get("tecido") and produto \
       and (slots_turno.get("tecido") or slots_turno.get("produto")) \
       and sinal_compat:
        return "combinado_tecido_em_produto"

    if slots_efetivos.get("cor") and slots_efetivos.get("tecido") \
       and (slots_turno.get("cor") or slots_turno.get("tecido")) \
       and sinal_compat:
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

    # ── 7b. Roteamento fino "produção vs outro setor" ─────────────
    # Os setores (setor_*) têm peso 9, então uma pergunta de PRODUÇÃO que só
    # menciona de passagem uma palavra de outro setor (envio, entrega, desconto,
    # fornecedor) era puxada pra lá — mesmo existindo uma intenção NOSSA com
    # resposta melhor. Aqui a gente segura essas na produção quando o contexto
    # é claramente do nosso setor. (Obs: "veio com defeito" continua indo pra
    # devoluções DE PROPÓSITO — a própria qualidade_defeito encaminha pra lá.)

    # Cuidado POR TECIDO: "como cuido/lavo do jeans" → cuidados_jeans (não o
    # catálogo de calças nem a composição). Exige verbo de cuidado + tecido.
    if re.search(r'cuid|lav|conserv|encolh|desbot|amass|ferro', t):
        for padrao, intent in (
            (r'\balgodao', 'cuidados_algodao'), (r'\bviscose', 'cuidados_viscose'),
            (r'\bpoliester', 'cuidados_poliester'), (r'\blinho', 'cuidados_linho'),
            (r'\bjeans', 'cuidados_jeans'), (r'\bmoletom', 'cuidados_moletom'),
            (r'\bmalha', 'cuidados_malha'), (r'\bla\b', 'cuidados_la'),
        ):
            if re.search(padrao, t):
                return intent

    # Envio de ARTE/arquivo pra personalização (não é logística de entrega).
    if re.search(r'\b(arte|arquivo|layout|vetor|png|cdr|pdf|svg)\b', t) and \
       re.search(r'envi|mand|form|aceit|resoluc', t):
        return "personalizacao_envio_arte"

    # Desconto por VOLUME → temos a tabela de progressão (não encaminha pra vendas).
    if (re.search(r'desconto', t) and re.search(
            r'volume|atacado|progressiv|quantidade|quanto mais|lote|por peca', t)) \
       or re.search(r'quanto mais.*barato', t):
        return "combinado_desconto_volume"

    # Revenda/atacadista → condições de revenda (não vendas genérico).
    if re.search(r'revend|atacadista|distribuidor|sacoleira', t):
        return "revenda"

    # Fornecedor/origem DO TECIDO → tec_origem (o setor de compras é pra quem
    # quer VENDER material PRA gente, não pra quem pergunta de onde vem o nosso).
    if re.search(r'(fornecedor|origem|de onde vem).{0,14}tecido|'
                 r'tecido (nacional|importado)|tecelagem|malharia', t):
        return "tec_origem"

    # "pronta entrega" é termo de produção (trabalhamos sob demanda), não logística.
    if re.search(r'pronta.?entrega|peca(s)? pronta|envio imediato', t):
        if re.search(r'\bcor(es)?\b', t):
            return "cores_basicas"
        return "pronta_entrega"

    # "prazo ... da produção/fabricação" é o nosso lead time, não prazo de envio.
    if re.search(r'\bprazo\b', t) and re.search(r'produc|fabricac', t):
        return "prazo_padrao"

    # ── 7c. Tópico perguntado vence o substantivo de produto ──────
    # "qual o prazo de uma camiseta" / "quais tamanhos de polo" caíam no CATÁLOGO
    # do produto (cat_* pesa 6; o menu do tópico pesa 4). Se a pessoa cita um
    # produto mas o que ela PERGUNTA é prazo/tamanho/urgência, respondemos o tópico.
    # (Fica DEPOIS das regras compostas: "prazo de 100 camisetas" com quantidade
    # já virou combinado lá em cima; grade explícita já virou tamanho_em_produto.)
    # (b2b de uniforme empresarial — "uniforme pra empresa com logo e prazo" —
    # não entra aqui: é pedido completo, tratado adiante.)
    contexto_b2b = bool(re.search(r'empresa|b2b|logo', t))
    if produto and not contexto_b2b:
        if re.search(r'\bprazo\b|quando fica|quanto tempo', t):
            return "prazo_padrao"
        if re.search(r'\btamanhos?\b|\bgrade\b|\bnumeracao\b', t):
            return "personalizacao_tamanhos"
        if slots_efetivos.get("urgente"):
            return "prazo_urgente"

    # ── 8. Palavras-chave do CSV (desempate por PESO) ─────────────
    # Antes era "a primeira intenção que bater vence". Agora coletamos TODAS as
    # intenções cuja palavra-chave aparece na frase e ficamos com a de MAIOR PESO.
    #
    # A busca exige FRONTEIRA DE PALAVRA à esquerda da keyword (\b) — senão
    # keywords curtas casam DENTRO de outras palavras e geram respostas absurdas:
    # "mano" dentro de "hu-mano", "vei" dentro de "dura-vei-s"/"sustenta-vei-s",
    # "cad" dentro de "a-cad-emia". O \b só na frente preserva plurais/sufixos
    # ("camiseta" ainda casa "camisetas"); keywords que começam com símbolo
    # (ex: "% algodao") mantêm a busca por substring.
    melhor_peso = -1.0
    melhor_kw = None
    for _, row in intencoes.iterrows():
        keywords = str(row["palavras_chave"]).strip()
        if not keywords or keywords == "nan":
            continue
        for kw in keywords.split("|"):
            kw = normalizar(kw.strip())
            if not kw:
                continue
            padrao = (r'\b' + re.escape(kw)) if kw[0].isalnum() else re.escape(kw)
            if re.search(padrao, t):
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
            # Keywords curtíssimas (≤3 letras: "vei", "bro", "dtf", "la") NÃO entram
            # no fuzzy: partial_ratio de 2-3 letras casa dentro de qualquer palavra
            # longa ("vei" em "sustenta-vei-s"/"dura-vei-s") e gera intenção absurda.
            # O match exato dessas já foi feito na etapa 8; aqui elas só dão ruído.
            if len(kw) < 4:
                continue
            # Mensagem MUITO mais curta que a keyword? Pula. Senão um token solto
            # casa 100% dentro de uma keyword composta ("preto" dentro de "tem
            # vestido preto") e cai numa intenção combinada sem os slots (→ "em None").
            # 0.5 bloqueia "preto"(5) vs "tem vestido preto"(17) mas libera
            # "produtos"(8) vs "quais produtos"(14).
            if len(t) < len(kw) * 0.5:
                continue
            score = fuzz.partial_ratio(kw, t)
            # vence o maior score; se empatar no score, vence o maior peso
            if score > melhor_score or (score == melhor_score and peso > melhor_peso):
                melhor_score = score
                melhor_peso = peso
                melhor_intencao = row["id_intencao"]

    if melhor_score >= 85:
        return melhor_intencao

    # ── 10. Antes de desistir: se a pessoa citou um PRODUTO ou TECIDO (sem uma
    # pergunta específica que casasse acima), mostramos o catálogo daquele
    # produto / o menu de tecidos — bem mais útil que o fallback puro.
    _CAT_POR_PRODUTO = {
        "camiseta_basica": "cat_camisetas", "camiseta_premium": "cat_camisetas",
        "polo": "cat_camisetas", "baby_look": "cat_camisetas",
        "regata": "cat_camisetas", "oversized": "cat_camisetas",
        "moletom": "cat_moletons", "jaqueta": "cat_moletons",
        "calca_jeans": "cat_calcas", "calca_alfaiataria": "cat_calcas",
        "legging": "cat_calcas", "bermuda": "cat_calcas", "jogger": "cat_calcas",
        "vestido_midi": "cat_vestidos", "vestido_longo": "cat_vestidos",
        "uniforme_polo": "cat_uniformes", "uniforme_jaleco": "cat_uniformes",
    }
    if produto in _CAT_POR_PRODUTO:
        return _CAT_POR_PRODUTO[produto]
    if slots_efetivos.get("tecido"):
        return "tecidos"

    return "fallback"
