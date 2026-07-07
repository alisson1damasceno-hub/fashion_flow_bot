"""
Geração da resposta a partir da intenção classificada + slots efetivos + dados.
"""
import re

from bot.normalizar import normalizar
# CRUD de pedidos — cada operação mora no seu próprio arquivo em bot/pedidos/.
from bot.pedidos import criar, consultar, atualizar, cancelar


def pecas(qtd):
    """Singular/plural correto (MÉDIO 26)."""
    return "peça" if qtd == 1 else "peças"


# ─────────────────────────── CRUD: coleta na conversa ───────────────────────────
# A lógica de CADA operação está em bot/pedidos/. O que fica aqui é só a parte de
# CONVERSA: perguntar os campos do registro um a um e descobrir o que alterar.

# Campos que precisamos coletar para registrar um pedido (na ordem das perguntas).
CAMPOS_REGISTRO = ["produto", "quantidade", "cor", "tamanho", "tecido", "personalizacao"]

PERGUNTAS_REGISTRO = {
    "produto": "Qual produto você quer produzir? (ex: camiseta, polo, moletom, vestido...)",
    "quantidade": "Quantas peças?",
    "cor": "Qual cor? (ex: preto, branco, marinho, vermelho...)",
    "tamanho": "Qual tamanho ou grade? (ex: M, G, infantil, plus size...)",
    "tecido": "Qual tecido? (ex: algodão, algodão pima, moletom flanelado, viscose...)",
    "personalizacao": "Qual personalização? (bordado, silk, DTF — ou responda 'nenhuma')",
}

# Palavras que abortam o registro no meio do caminho.
ABORTAR_REGISTRO = {"cancelar", "parar", "sair", "deixa pra la", "esquece", "esquecer", "desistir"}


def _valor_cru(mensagem, campo):
    """
    Quando o extractor não reconhece a resposta do campo perguntado, usamos o
    texto cru da mensagem. Para 'quantidade', pegamos só o primeiro número.
    """
    t = (mensagem or "").strip()
    if campo == "quantidade":
        m = re.search(r"\d+", t)
        return m.group(0) if m else None
    if campo == "tamanho":
        # Tamanhos curtos (P, M, G, GG, XGG) ficam em maiúsculo; grades por
        # extenso (infantil, plus size) ficam em minúsculo.
        return t.upper() if len(t) <= 3 else normalizar(t)
    return normalizar(t) or None


def _fluxo_registrar(slots, sessao, mensagem):
    """
    CREATE conversacional: coleta os campos do pedido ao longo da conversa e,
    quando tudo está preenchido, chama criar.registrar_pedido (que grava no CSV).
    """
    if sessao is None:
        return "Não consegui iniciar o registro agora."

    # Permite abortar o registro a qualquer momento.
    if normalizar(mensagem).strip() in ABORTAR_REGISTRO:
        sessao["registro_pedido"] = None
        sessao["registro_campo_pendente"] = None
        return "Tudo bem, cancelei o registro do pedido. Posso ajudar em outra coisa?"

    primeiro = sessao.get("registro_pedido") is None
    reg = sessao.get("registro_pedido") or {}

    # 1. Aproveita qualquer campo que o extractor reconheceu nesta mensagem.
    for campo in CAMPOS_REGISTRO:
        if slots.get(campo) not in (None, ""):
            reg[campo] = slots[campo]

    # 2. Se estávamos esperando um campo específico e o extractor não pegou,
    #    usa o texto cru da resposta (ex: "M" para tamanho, "nenhuma" p/ personalização).
    pendente = sessao.get("registro_campo_pendente")
    if pendente and not reg.get(pendente) and not primeiro:
        cru = _valor_cru(mensagem, pendente)
        if cru:
            reg[pendente] = cru

    sessao["registro_pedido"] = reg

    # 3. Ainda falta algum campo? Pergunta o próximo.
    faltando = [c for c in CAMPOS_REGISTRO if not reg.get(c)]
    if faltando:
        proximo = faltando[0]
        sessao["registro_campo_pendente"] = proximo
        intro = "Vamos registrar seu pedido! " if primeiro else ""
        return intro + PERGUNTAS_REGISTRO[proximo]

    # 4. Completou → grava no CSV e encerra o fluxo de registro.
    sessao["registro_campo_pendente"] = None
    sessao["registro_pedido"] = None
    reg["cliente"] = sessao.get("nome_cliente", "")   # o dono é o nome da conversa
    return criar.registrar_pedido(reg)["mensagem"]


def _detectar_alteracao(mensagem, slots):
    """
    Descobre qual campo o cliente quer mudar e para qual valor novo.
    Retorna (campo, valor) ou (None, None) se não der pra inferir.

    Duas regras que consertam o bug do "mudou de 'preto' para 'preto'":
    - O valor NOVO é o que vem depois de "para/pra" — em "de algodão PARA linho",
      o alvo é linho (o primeiro tecido citado costuma ser o valor ATUAL).
    - Re-extrai da própria mensagem (sem herdar o contexto), senão pegava uma
      cor/tecido velho da conversa e "alterava" pro mesmo valor.
    """
    from bot.extractor import extrair_slots

    t = normalizar(mensagem)
    m_alvo = re.search(r'\b(?:para|pra|pro)\s+(.+)$', t)
    alvo = extrair_slots(m_alvo.group(1)) if m_alvo else {}   # valor depois de "para"
    aqui = extrair_slots(mensagem)                            # slots ditos AGORA (sem contexto)

    def val(chave):
        return alvo.get(chave) if alvo.get(chave) is not None else aqui.get(chave)

    # 1. Campo dito por extenso na frase ("mudar o TECIDO para linho").
    if "tecido" in t and val("tecido") is not None:
        return "tecido", val("tecido")
    if "cor" in t and val("cor") is not None:
        return "cor", val("cor")
    if "tamanho" in t and val("grade") is not None:
        return "tamanho", val("grade")
    if "quantidade" in t or "quantas" in t:
        q = val("quantidade")
        if q is None and m_alvo:            # "mudar a quantidade para 200" (sem unidade)
            m_num = re.search(r'\d+', m_alvo.group(1))
            q = int(m_num.group()) if m_num else None
        if q is not None:
            return "quantidade", q
    if "personaliza" in t and val("personalizacao") is not None:
        return "personalizacao", val("personalizacao")

    # 2. Sem o nome do campo: infere pelo ALVO (o que vem depois de "para").
    for campo, chave in (("tecido", "tecido"), ("cor", "cor"), ("quantidade", "quantidade"),
                         ("personalizacao", "personalizacao"), ("tamanho", "grade")):
        if alvo.get(chave) is not None:
            return campo, alvo[chave]

    # 3. Último recurso: um único slot dito na própria mensagem.
    for campo, chave in (("tecido", "tecido"), ("cor", "cor"), ("quantidade", "quantidade"),
                         ("personalizacao", "personalizacao")):
        if aqui.get(chave) is not None:
            return campo, aqui[chave]
    return None, None


def responder(intencao, slots, dados, sessao=None, mensagem=""):
    """
    Retorna a resposta em texto para o usuário.
    `slots` aqui são os slots EFETIVOS (foco_atual + slots_turno mesclados).
    """

    # ── CREATE: registrar pedido (coleta os campos ao longo da conversa) ──
    if intencao == "registrar_pedido":
        return _fluxo_registrar(slots, sessao, mensagem)

    # ── Seleção de menu ──────────────────────────────────────────
    if intencao == "selecao_opcao":
        from rapidfuzz import fuzz

        opcao_menu = sessao.get("aguardando_opcao") if sessao else None
        # Mapa completo de menus, mesclando nosso (tecido/produto) com a versão
        # expandida da equipe (qualidade, personalização, sustentabilidade etc).
        opcoes_por_menu = {
            "menu_tecido": {
                "algodao basico": "algodao_basico", "algodao penteado": "algodao_penteado",
                "algodao pima": "algodao_pima", "dry fit": "dry_fit", "viscose": "viscose",
                "suplex": "suplex", "moletom flanelado": "moletom_flanelado",
                "moletom peluciado": "moletom_peluciado", "malha mista": "malha_mista",
                "linho": "linho", "jeans": "jeans", "alfaiataria": "alfaiataria",
            },
            "menu_produto": {
                "camiseta basica": "camiseta_basica", "camiseta premium": "camiseta_premium",
                "polo": "polo", "baby look": "baby_look", "moletom": "moletom",
                "jaqueta": "jaqueta", "calca jeans": "calca_jeans", "legging": "legging",
                "bermuda": "bermuda", "regata": "regata", "vestido midi": "vestido_midi",
                "jogger": "jogger", "uniforme polo": "uniforme_polo",
                "uniforme jaleco": "uniforme_jaleco", "oversized": "oversized",
            },
            "menu_qualidade": {
                "originalidade das pecas": "qualidade_originalidade",
                "durabilidade":            "qualidade_durabilidade",
                "controle de qualidade":   "qualidade_controle",
                "defeitos de fabricacao":  "qualidade_defeito",
                "certificacoes":           "qualidade_certificacoes",
            },
            "menu_personalizacao": {
                "tipos de personalizacao":  "personalizacao_tipos",
                "cores disponiveis":        "personalizacao_cores",
                "tamanhos disponiveis":     "personalizacao_tamanhos",
                "quantidade minima":        "personalizacao_quantidade",
                "prazo de personalizacao":  "personalizacao_prazo",
                "envio de arte":            "personalizacao_envio_arte",
            },
            "menu_personalizacao_tipos": {
                "estampa silkscreen":     "personalizacao_silkscreen",
                "estampa dtf digital":    "personalizacao_dtf",
                "bordado":                "personalizacao_bordado",
                "etiqueta personalizada": "personalizacao_etiqueta",
                "modelagem exclusiva":    "personalizacao_modelagem_exclusiva",
            },
            "menu_personalizacao_cores": {
                "cores basicas em estoque":    "cores_basicas",
                "tingimento sob demanda":      "cores_sob_demanda",
                "combinacao cor peca estampa": "cores_combinacao",
                "limite de cores por tecnica": "cores_limite_tecnica",
            },
            "menu_personalizacao_tamanhos": {
                "grade adulto":      "tamanhos_adulto",
                "grade infantil":    "tamanhos_infantil",
                "plus size":         "tamanhos_plus_size",
                "tabela de medidas": "tamanhos_tabela_medidas",
            },
            "menu_personalizacao_quantidade": {
                "minimo por tipo de personalizacao": "qtd_minima_personalizacao",
                "minimo por cor":                    "qtd_minima_cor",
                "pedidos grandes 500":               "qtd_grande_volume",
                "pedidos pequenos ate 30":           "qtd_pequena_volume",
            },
            "menu_sustentabilidade": {
                "aproveitamento de tecido": "sustent_aproveitamento",
                "materiais sustentaveis":   "sustent_materiais_eco",
                "reciclagem de sobras":     "sustent_reciclagem",
                "tinturas e quimicos":      "sustent_quimicos",
                "praticas trabalhistas":    "sustent_trabalho",
                "logistica sustentavel":    "sustent_logistica",
            },
            "menu_manutencao": {
                "como lavar":         "manut_lavar",
                "ferro de passar":    "manut_ferro",
                "secadora":           "manut_secadora",
                "alvejante":          "manut_alvejante",
                "tirar mancha":       "manut_mancha",
                "cuidados por tecido":"manut_por_tecido",
                "encolhimento":       "manut_encolhimento",
                "desbotamento":       "manut_desbotamento",
            },
            "menu_manut_por_tecido": {
                "algodao":   "cuidados_algodao",
                "viscose":   "cuidados_viscose",
                "poliester": "cuidados_poliester",
                "linho":     "cuidados_linho",
                "jeans":     "cuidados_jeans",
                "la":        "cuidados_la",
                "malha":     "cuidados_malha",
                "moletom":   "cuidados_moletom",
            },
            "menu_producao": {
                "etapas do processo":   "producao_etapas",
                "onde e produzido":     "producao_onde",
                "capacidade produtiva": "producao_capacidade",
                "tecnologia":           "producao_tecnologia",
                "equipe":               "producao_equipe",
                "modelagem":            "producao_modelagem",
                "corte e costura":      "producao_corte_costura",
            },
            "menu_catalogo": {
                "camisetas e basicas":    "cat_camisetas",
                "moletons e jaquetas":    "cat_moletons",
                "calcas e shorts":        "cat_calcas",
                "vestidos":               "cat_vestidos",
                "uniformes corporativos": "cat_uniformes",
                "linha infantil":         "cat_infantil",
            },
            "menu_sugestao_produto": {
                "casual dia a dia":       "sug_casual",
                "trabalho corporativo":   "sug_trabalho",
                "esporte academia":       "sug_esporte",
                "festa ocasiao especial": "sug_festa",
                "inverno":                "sug_inverno",
                "verao":                  "sug_verao",
                "uniforme empresa":       "sug_uniforme",
                "presente":               "sug_presente",
            },
            "menu_tecidos": {
                "lista de tecidos disponiveis": "tec_disponiveis",
                "composicao de cada peca":      "tec_composicao",
                "origem dos tecidos":           "tec_origem",
                "sugestao por uso":             "sug_tecido_uso",
                "tecido para pele sensivel":    "tec_pele_sensivel",
                "nao trabalhamos com":          "tec_couro",
            },
            "menu_sug_tecido_uso": {
                "clima quente":   "sug_tec_quente",
                "clima frio":     "sug_tec_frio",
                "uso diario":     "sug_tec_diario",
                "esporte":        "sug_tec_esporte",
                "ocasiao formal": "sug_tec_formal",
            },
            "menu_previsao_prazo": {
                "prazo padrao":       "prazo_padrao",
                "com personalizacao": "prazo_com_personalizacao",
                "pedido urgente":     "prazo_urgente",
                "pedido grande 500":  "prazo_grande_pedido",
                "atraso de pedido":   "prazo_atraso",
            },
            "menu_etapas_pedido": {
                "em que etapa esta":        "etapa_consulta",
                "alterar pedido":           "alterar_pedido",
                "cancelar pedido":          "cancelar_pedido",
                "acompanhamento detalhado": "acompanhamento",
            },
        }
        opcoes = opcoes_por_menu.get(opcao_menu, {})

        # usuário digitou um número
        try:
            numero = int(mensagem.strip())
            lista = list(opcoes.values())
            if 1 <= numero <= len(lista):
                escolha = lista[numero - 1]
                if sessao:
                    # MÉDIO 15: não persiste no foco_atual; só limpa o menu.
                    sessao["aguardando_opcao"] = None
                df_int = dados["intencoes"]
                row_sub = df_int[df_int["id_intencao"] == escolha]
                if not row_sub.empty:
                    return row_sub.iloc[0]["resposta_padrao"]
                return f"Entendido! Registrei: {escolha.replace('_', ' ')}. Como posso continuar te ajudando?"
        except (ValueError, TypeError):
            pass

        # usuário digitou o nome
        melhor_score = 0
        melhor_valor = None
        msg_norm = normalizar(mensagem)
        for chave, valor in opcoes.items():
            score = fuzz.partial_ratio(normalizar(chave), msg_norm)
            if score > melhor_score:
                melhor_score = score
                melhor_valor = valor

        if melhor_score >= 75:
            if sessao:
                sessao["aguardando_opcao"] = None
            df_int = dados["intencoes"]
            row_sub = df_int[df_int["id_intencao"] == melhor_valor]
            if not row_sub.empty:
                return row_sub.iloc[0]["resposta_padrao"]
            return f"Entendido! Registrei: {melhor_valor.replace('_', ' ')}. Como posso continuar te ajudando?"

        # Não casou nenhuma opção. Antes isso virava um beco-sem-saída ("Não
        # entendi sua escolha" repetido) e o cliente ficava preso no menu. Agora
        # a gente SAI do menu e trata a mensagem como uma pergunta nova — a pessoa
        # provavelmente mudou de assunto ("me explica o silk") ou escolheu por
        # uma frase que não é o rótulo exato ("tem vegano?"). Conserta o "menu sem saída".
        from bot.extractor import extrair_slots
        from bot.contexto import merge_com_contexto
        from bot.classifier import classificar

        if sessao:
            sessao["aguardando_opcao"] = None
        slots_novos = extrair_slots(mensagem, em_menu=False)
        slots_ef = merge_com_contexto(slots_novos, sessao) if sessao else slots_novos
        nova_intencao = classificar(mensagem, slots_novos, slots_ef, dados["intencoes"], sessao)
        if nova_intencao not in ("selecao_opcao", "fallback"):
            return responder(nova_intencao, slots_ef, dados, sessao, mensagem)

        # Nem como pergunta nova deu — aí sim mostra o menu de novo pra ajudar.
        if sessao:
            sessao["aguardando_opcao"] = opcao_menu
        lista_opcoes = "\n".join(f"  {i+1}. {c.title()}" for i, c in enumerate(opcoes.keys()))
        return f"Não entendi sua escolha. Por favor, selecione uma opção:\n{lista_opcoes}"

    # ── Prazo sem contexto (cenário 12) ──────────────────────────
    if intencao == "prazo_sem_contexto":
        prazo = slots.get("prazo_desejado", 0)
        return (
            f"Vi que você mencionou {prazo} dias — pra eu dizer se conseguimos, preciso saber: "
            "qual produto, qual quantidade e se tem personalização (silk, bordado, DTF)?"
        )

    # ── DELETE: cancelar pedido (soft delete) ────────────────────
    if intencao == "cancelar_pedido":
        numero = slots.get("numero_pedido")
        if not numero:
            # Ainda não temos o ID → pergunta e guarda a ação como pendente.
            if sessao is not None:
                sessao["aguardando_id"] = "cancelar_pedido"
            return (
                "Pra cancelar, me informa o número do pedido (formato FF-AAAA-NNNN). "
                "Aviso: cancelamento é livre na modelagem; depois do corte pode haver "
                "custo de material já usado."
            )
        if sessao is not None:
            sessao["aguardando_id"] = None
        return cancelar.cancelar_pedido(numero, sessao.get("nome_cliente") if sessao else None)["mensagem"]

    # ── Disponibilidade de materiais / estoque (CRÍTICO 5) ──────
    if intencao == "disponibilidade_materiais":
        tecido = slots.get("tecido")
        df = dados["estoque_materiais"]
        if tecido:
            row = df[df["tecido"] == tecido]
            if not row.empty:
                r = row.iloc[0]
                if r["status"] == "disponivel":
                    return (
                        f"Sim, temos {tecido.replace('_', ' ')} em estoque: "
                        f"{r['metros_disponivel']}m disponíveis. {r['observacao']}."
                    )
                else:
                    return (
                        f"No momento {tecido.replace('_', ' ')} está sem estoque. "
                        f"Previsão de reposição: {r['previsao_reposicao']}. {r['observacao']}."
                    )
        # sem tecido específico — visão geral
        disponiveis = df[df["status"] == "disponivel"]["tecido"].tolist()
        indispon = df[df["status"] == "indisponivel"]["tecido"].tolist()
        return (
            "Visão geral de estoque: "
            f"disponíveis ({len(disponiveis)}) — {', '.join(t.replace('_',' ') for t in disponiveis[:6])}"
            + (f"... + {len(disponiveis)-6} outros." if len(disponiveis) > 6 else ".")
            + (f" Indisponíveis: {', '.join(t.replace('_',' ') for t in indispon)}." if indispon else "")
        )

    # ── READ: consultar pedido por ID ────────────────────────────
    if intencao == "status_pedido":
        numero = slots.get("numero_pedido")
        if not numero:
            # Não veio o ID → pergunta e marca que estamos esperando ele.
            if sessao is not None:
                sessao["aguardando_id"] = "status_pedido"
            return (
                "Claro! Me informa o número do pedido que eu consulto o andamento na "
                "produção. O formato é FF-AAAA-NNNN (ex: FF-2026-0001)."
            )
        if sessao is not None:
            sessao["aguardando_id"] = None
        return consultar.consultar_pedido(numero, sessao.get("nome_cliente") if sessao else None)["mensagem"]

    # ── UPDATE: alterar um campo do pedido ───────────────────────
    if intencao == "alterar_pedido_especifico":
        numero = slots.get("numero_pedido")
        campo, valor = _detectar_alteracao(mensagem, slots)
        # Recupera a alteração que guardamos enquanto pedíamos o ID.
        if (campo is None or valor is None) and sessao and sessao.get("alteracao_pendente"):
            campo = sessao["alteracao_pendente"].get("campo")
            valor = sessao["alteracao_pendente"].get("valor")
        if not numero:
            # Falta o ID → pergunta e guarda o que o cliente quer mudar.
            if sessao is not None:
                sessao["aguardando_id"] = "alterar_pedido_especifico"
                sessao["alteracao_pendente"] = {"campo": campo, "valor": valor}
            return (
                "Pra alterar, me informa o número do pedido (FF-AAAA-NNNN). Lembrando: "
                "só dá pra alterar enquanto está na etapa de modelagem."
            )
        if sessao is not None:
            sessao["aguardando_id"] = None
        if not campo or valor is None:
            if sessao is not None:
                sessao["alteracao_pendente"] = None
            return (
                f"O que você quer mudar no pedido {numero}? Posso alterar cor, tamanho, "
                "quantidade, tecido ou personalização — e me diz pro quê. "
                "Ex: 'mudar a cor para branco'."
            )
        resultado = atualizar.alterar_campo(numero, campo, valor, sessao.get("nome_cliente") if sessao else None)
        if sessao is not None:
            sessao["alteracao_pendente"] = None
        return resultado["mensagem"]

    # Obs: NÃO existe handler de "avançar etapa" aqui. Avançar a peça na esteira
    # (modelagem -> corte -> ...) é ação da produção interna, não do cliente. A
    # função atualizar.avancar_etapa existe e é testada, mas não é exposta no chat.

    # ── Viabilidade de produção ──────────────────────────────────
    if intencao == "viabilidade_producao":
        quantidade = slots.get("quantidade", 0)
        tecido = slots.get("tecido")
        prazo = slots.get("prazo_desejado")
        urgente = slots.get("urgente", False)

        df_cap = dados["capacidade_produtiva"]
        df_est = dados["estoque_materiais"]

        costura = df_cap[df_cap["setor"] == "costura"].iloc[0]
        cap_disponivel = int(costura["disponivel_hoje_pecas"])
        viavel_capacidade = quantidade <= cap_disponivel

        material_msg = ""
        material_ok = True
        if tecido:
            row_mat = df_est[df_est["tecido"] == tecido]
            if not row_mat.empty:
                r = row_mat.iloc[0]
                material_ok = r["status"] == "disponivel"
                if not material_ok:
                    material_msg = (
                        f" Porém, {tecido.replace('_', ' ')} está sem estoque "
                        f"(reposição em {r['previsao_reposicao']})."
                    )
                else:
                    material_msg = (
                        f" {tecido.replace('_', ' ').title()} disponível "
                        f"({r['metros_disponivel']}m em estoque)."
                    )

        aviso_urgencia = ""
        if urgente:
            aviso_urgencia = " Notei que é urgente — taxa de urgência aplicada é de 20% a 40%."

        if prazo and prazo < 15:
            return (
                f"Para {quantidade} {pecas(quantidade)} em {prazo} dias: nosso prazo mínimo é de "
                "15 dias úteis (sem personalização). "
                f"A capacidade do setor de costura é de {cap_disponivel} peças/dia.{material_msg}{aviso_urgencia} "
                "Para esse prazo, vendas avalia taxa de urgência."
            )

        if viavel_capacidade and material_ok:
            return (
                f"Sim, temos capacidade técnica para produzir {quantidade} {pecas(quantidade)}. "
                f"O setor de costura tem {cap_disponivel} peças disponíveis hoje.{material_msg}{aviso_urgencia} "
                "Para confirmar, fale com vendas."
            )
        else:
            motivos = []
            if not viavel_capacidade:
                motivos.append(
                    f"a capacidade disponível hoje é de {cap_disponivel} peças "
                    f"e você solicitou {quantidade}"
                )
            if not material_ok:
                motivos.append(material_msg.strip())
            return (
                f"Pode haver dificuldades para produzir {quantidade} {pecas(quantidade)} agora: "
                f"{'; '.join(motivos)}.{aviso_urgencia} "
                "Fale com vendas para avaliar alternativas."
            )

    # ── Consumo de tecido ────────────────────────────────────────
    if intencao == "consumo_tecido":
        quantidade = slots.get("quantidade", 0)
        produto = slots.get("produto")
        tecido = slots.get("tecido")
        metragem = slots.get("metragem", 0)

        df = dados["consumo_tecido"]
        filtro = df[df["produto"] == produto]
        if tecido:
            filtro_tec = filtro[filtro["tecido_principal"] == tecido]
            if not filtro_tec.empty:
                filtro = filtro_tec

        if filtro.empty:
            return (
                f"Não tenho dados de consumo para {produto or 'esse produto'}. "
                "Fale com o setor técnico."
            )

        metros_por_peca = float(filtro.iloc[0]["metros_por_peca"])
        metros_necessarios = round(metros_por_peca * quantidade, 2)
        obs = filtro.iloc[0]["observacao"]

        if metragem > 0:
            if metragem >= metros_necessarios:
                sobra = round(metragem - metros_necessarios, 2)
                return (
                    f"Para {quantidade} {pecas(quantidade)} de {produto.replace('_',' ')}, "
                    f"precisa de {metros_necessarios}m ({metros_por_peca}m por peça). "
                    f"Com {metragem}m você tem o suficiente — sobram {sobra}m. Obs: {obs}"
                )
            else:
                falta = round(metros_necessarios - metragem, 2)
                return (
                    f"Para {quantidade} {pecas(quantidade)} de {produto.replace('_',' ')}, "
                    f"precisa de {metros_necessarios}m ({metros_por_peca}m por peça). "
                    f"Com apenas {metragem}m, faltam {falta}m. Obs: {obs}"
                )

        return (
            f"Para {quantidade} {pecas(quantidade)} de {produto.replace('_',' ')}, "
            f"precisa de aproximadamente {metros_necessarios}m ({metros_por_peca}m por peça). Obs: {obs}"
        )

    # ── Prazo ────────────────────────────────────────────────────
    if intencao == "combinado_prazo_qtd_produto":
        quantidade = slots.get("quantidade", 0)
        produto = slots.get("produto")
        personalizacao = slots.get("personalizacao", "nenhuma")
        urgente = slots.get("urgente", False)
        prazo_desejado = slots.get("prazo_desejado")
        # ALTO 30: produto inexistente vira esclarecimento
        if not produto:
            return (
                "Pra calcular prazo eu preciso saber qual produto você quer. "
                "Trabalhamos com camisetas, polos, moletons, vestidos, calças, uniformes e mais. "
                "Qual deles?"
            )

        df = dados["prazo"]
        filtro = df[
            (df["produto"] == produto) &
            (df["qtd_min"] <= quantidade) &
            (df["qtd_max"] >= quantidade) &
            (df["personalizacao"] == personalizacao)
        ]
        if filtro.empty:
            filtro = df[
                (df["produto"] == produto) &
                (df["qtd_min"] <= quantidade) &
                (df["qtd_max"] >= quantidade)
            ]
        if filtro.empty:
            # MÉDIO 31: mensagem específica pra quantidades muito altas
            qtd_max = df[df["produto"] == produto]["qtd_max"].max() if not df[df["produto"] == produto].empty else 0
            if quantidade > qtd_max:
                return (
                    f"{quantidade} peças é um pedido grande — acima da nossa tabela padrão "
                    f"(máximo tabelado: {qtd_max}). Pra esse volume é orçamento especial com vendas, "
                    "geralmente em fases (lotes de 100-200 peças) e prazo planejado."
                )
            return (
                f"Não encontrei dados de prazo para {produto.replace('_',' ')} com quantidade {quantidade}. "
                "Fale com vendas pra estimativa personalizada."
            )
        r = filtro.iloc[0]
        pers_txt = f" com {personalizacao}" if personalizacao != "nenhuma" else ""
        prazo_min = int(r['prazo_min_dias'])
        prazo_max = int(r['prazo_max_dias'])

        aviso = ""
        # MÉDIO 17 + urgência: usa o slot urgente que estava sendo ignorado
        if urgente or (prazo_desejado and prazo_desejado < prazo_min):
            aviso = (
                f" Pelo prazo desejado ({prazo_desejado} dias) ser mais curto que o normal, "
                if prazo_desejado and prazo_desejado < prazo_min else " Notei que é urgente — "
            ) + "aplicamos taxa de urgência de 20% a 40%. Fale com vendas pra avaliar."

        return (
            f"Para {quantidade} {pecas(quantidade)} de {produto.replace('_',' ')}{pers_txt}: "
            f"prazo estimado de {prazo_min} a {prazo_max} dias úteis.{aviso} "
            "Prazo confirmado pelo setor de vendas no fechamento do pedido."
        )

    # ── Preço ────────────────────────────────────────────────────
    if intencao == "combinado_preco_qtd_produto":
        quantidade = slots.get("quantidade", 0)
        produto = slots.get("produto")
        personalizacao = slots.get("personalizacao", "nenhuma")
        if not produto:
            return (
                "Pra calcular preço eu preciso saber qual produto você quer. "
                "Trabalhamos com camisetas, polos, moletons, vestidos, calças, uniformes e mais. "
                "Qual deles?"
            )

        df = dados["preco"]
        filtro = df[
            (df["produto"] == produto) &
            (df["qtd_min"] <= quantidade) &
            (df["qtd_max"] >= quantidade) &
            (df["personalizacao"] == personalizacao)
        ]
        if filtro.empty:
            filtro = df[
                (df["produto"] == produto) &
                (df["qtd_min"] <= quantidade) &
                (df["qtd_max"] >= quantidade)
            ]
        if filtro.empty:
            qtd_max = df[df["produto"] == produto]["qtd_max"].max() if not df[df["produto"] == produto].empty else 0
            if quantidade > qtd_max:
                return (
                    f"{quantidade} peças é um volume bem grande — fora da nossa tabela "
                    f"(máximo: {qtd_max}). Pra esse pedido vale orçamento especial com vendas, "
                    "tem desconto progressivo a partir de 500 peças."
                )
            return (
                f"Não encontrei dados de preço para {produto.replace('_',' ')} com quantidade {quantidade}. "
                "Fale com vendas pra orçamento personalizado."
            )
        r = filtro.iloc[0]
        total = round(float(r["preco_unitario_estimado"]) * quantidade, 2)
        pers_txt = f" com {personalizacao}" if personalizacao != "nenhuma" else ""
        return (
            f"Para {quantidade} {pecas(quantidade)} de {produto.replace('_',' ')}{pers_txt}: "
            f"valor unitário estimado de R$ {r['preco_unitario_estimado']} "
            f"({r['desconto_aplicado']} de desconto). "
            f"Total estimado: R$ {total:.2f}. "
            "Valor indicativo — fechamento com vendas."
        )

    # ── Compatibilidade tecido × personalização ──────────────────
    if intencao == "combinado_personalizacao_em_tecido":
        tecido = slots.get("tecido")
        personalizacao = slots.get("personalizacao")
        df = dados["compat_tecido_personalizacao"]
        filtro = df[(df["tecido"] == tecido) & (df["personalizacao"] == personalizacao)]
        if filtro.empty:
            return f"Não tenho dados sobre {personalizacao} em {tecido}. Consulte o setor técnico."
        r = filtro.iloc[0]
        obs = str(r["observacao"]).strip()
        obs = obs[:1].upper() + obs[1:] if obs else obs
        if r["compativel"].strip().lower() == "sim":
            return f"Sim! {obs}"
        return obs

    # ── Compatibilidade tecido × produto ─────────────────────────
    if intencao == "combinado_tecido_em_produto":
        tecido = slots.get("tecido")
        produto = slots.get("produto")
        df = dados["compat_tecido_produto"]
        filtro = df[(df["tecido"] == tecido) & (df["produto"] == produto)]
        if filtro.empty:
            return f"Não tenho dados sobre {tecido} em {produto}. Consulte o setor técnico."
        r = filtro.iloc[0]
        obs = str(r["observacao"]).strip()
        obs = obs[:1].upper() + obs[1:] if obs else obs
        if r["compativel"].strip().lower() == "sim":
            return f"Sim! {obs}"
        return obs

    # ── Quais tecidos combinam com um produto ────────────────────
    # (Antes esse id tinha uma resposta PLACEHOLDER de dev no CSV — "Consultar
    # lookup... e listar". Agora lista de verdade os tecidos compatíveis.)
    if intencao == "combinado_tecidos_disponiveis_para_produto":
        produto = slots.get("produto")
        if not produto:
            return ("Pra qual produto? (ex: camiseta, moletom, calça, vestido...) "
                    "Aí eu listo os tecidos que combinam.")
        df = dados["compat_tecido_produto"]
        compat = df[(df["produto"] == produto)
                    & (df["compativel"].str.strip().str.lower() == "sim")]
        if compat.empty:
            return (f"Não tenho tecidos cadastrados como ideais para "
                    f"{produto.replace('_',' ')}. Consulte o setor técnico.")
        tecidos = ", ".join(t.replace("_", " ") for t in compat["tecido"].tolist())
        return f"Para {produto.replace('_',' ')}, os tecidos recomendados são: {tecidos}."

    # ── Cor em tecido ────────────────────────────────────────────
    if intencao == "combinado_cor_em_tecido":
        cor = slots.get("cor")
        tecido = slots.get("tecido")
        # Sem tecido (ou sem cor) não dá pra consultar a matriz cor×tecido — e a
        # gente NÃO pode responder "... em None". A pessoa provavelmente só citou
        # uma cor: mostramos a paleta em estoque (cores_basicas).
        if not tecido or not cor:
            linha = dados["intencoes"][dados["intencoes"]["id_intencao"] == "cores_basicas"]
            if not linha.empty:
                return linha.iloc[0]["resposta_padrao"]
            return ("Me diz a cor e o tecido (ex: 'preto em algodão') que eu confiro a "
                    "disponibilidade — ou pergunta pelas cores em estoque.")
        df = dados["cor_tecido"]
        filtro = df[(df["tecido"] == tecido) & (df["cor"] == cor)]
        if filtro.empty:
            return (f"Não tenho dados sobre a cor {cor.replace('_',' ')} em "
                    f"{tecido.replace('_',' ')}. Consulte o setor de vendas.")
        r = filtro.iloc[0]
        disp = "em estoque permanente" if r["disponibilidade"] == "estoque" else "sob demanda (mínimo 80 peças + 7 a 10 dias)"
        return f"A cor {cor.replace('_',' ')} em {tecido.replace('_',' ')} está {disp}."

    # ── Gramatura ────────────────────────────────────────────────
    if intencao == "combinado_gramatura_produto_uso":
        produto = slots.get("produto")
        uso = slots.get("uso")
        df = dados["gramatura"]
        filtro = df[df["produto"] == produto]
        if uso:
            filtro_uso = filtro[filtro["uso"] == uso]
            if not filtro_uso.empty:
                filtro = filtro_uso
        if filtro.empty:
            return f"Não tenho dados de gramatura para {produto}. Consulte o setor técnico."
        r = filtro.iloc[0]
        return (
            f"Gramatura recomendada para {produto.replace('_',' ')} "
            f"({r['uso']}): {r['gramatura_min_g_m2']} a {r['gramatura_max_g_m2']} g/m². "
            f"{r['observacao']}"
        )

    # ── Tamanho / grade ──────────────────────────────────────────
    if intencao == "combinado_tamanho_em_produto":
        produto = slots.get("produto")
        grade = slots.get("grade")
        df = dados["tamanho_produto"]
        filtro = df[(df["produto"] == produto) & (df["grade"] == grade)]
        if filtro.empty:
            return f"Não tenho dados de grade {grade} para {produto}. Consulte o setor de vendas."
        r = filtro.iloc[0]
        disp = "disponível" if r["disponivel"] == "sim" else "não disponível"
        return (
            f"Grade {grade.replace('_',' ')} para {produto.replace('_',' ')}: {disp}. "
            f"{r['observacao']}"
        )

    # ── Resposta padrão do CSV (menus etc) ───────────────────────
    df_int = dados["intencoes"]
    row = df_int[df_int["id_intencao"] == intencao]
    if not row.empty:
        resposta = row.iloc[0]["resposta_padrao"]
        followup = row.iloc[0]["pergunta_followup"]
        if followup and str(followup) != "nan":
            if "|" in str(followup):
                if sessao:
                    sessao["aguardando_opcao"] = f"menu_{intencao}"
                opcoes = str(followup).split("|")
                lista = "\n".join(f"  {i+1}. {o.strip()}" for i, o in enumerate(opcoes))
                return f"{resposta}\n{lista}"
            return f"{resposta}\n{followup}"
        return resposta

    # ── Fallback ─────────────────────────────────────────────────
    return (
        "Não entendi bem sua pergunta. Posso ajudar com: "
        "prazos, preços, tecidos, personalização, compatibilidade, "
        "gramatura, tamanhos e status de pedidos. Pode reformular?"
    )
