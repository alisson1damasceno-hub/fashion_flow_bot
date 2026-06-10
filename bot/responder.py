"""
Geração da resposta a partir da intenção classificada + slots efetivos + dados.
"""
import unicodedata


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def pecas(qtd):
    """Singular/plural correto (MÉDIO 26)."""
    return "peça" if qtd == 1 else "peças"


def responder(intencao, slots, dados, sessao=None, mensagem=""):
    """
    Retorna a resposta em texto para o usuário.
    `slots` aqui são os slots EFETIVOS (foco_atual + slots_turno mesclados).
    """

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

        # não entendeu — mostra o menu de novo
        lista_opcoes = "\n".join(f"  {i+1}. {c.title()}" for i, c in enumerate(opcoes.keys()))
        return f"Não entendi sua escolha. Por favor, selecione uma opção:\n{lista_opcoes}"

    # ── Prazo sem contexto (cenário 12) ──────────────────────────
    if intencao == "prazo_sem_contexto":
        prazo = slots.get("prazo_desejado", 0)
        return (
            f"Vi que você mencionou {prazo} dias — pra eu dizer se conseguimos, preciso saber: "
            "qual produto, qual quantidade e se tem personalização (silk, bordado, DTF)?"
        )

    # ── Cancelar pedido (CRÍTICO 6) ──────────────────────────────
    if intencao == "cancelar_pedido":
        numero = slots.get("numero_pedido")
        df = dados["pedidos"]
        etapas_abertas = df[df["pode_alterar"] == "sim"]["etapa"].tolist()
        etapas_fechadas = df[df["pode_alterar"] == "nao"]["etapa"].tolist()
        if numero:
            return (
                f"Para cancelar o pedido {numero}, fale com o setor de vendas o mais rápido possível. "
                f"Cancelamento é viável enquanto o pedido está em: {', '.join(etapas_abertas)}. "
                f"Depois disso ({', '.join(etapas_fechadas)}), só negociação caso a caso — pode haver "
                "custo de material já consumido."
            )
        return (
            "Para cancelar um pedido, informe o número (formato FF-AAAA-NNNN) e fale com vendas. "
            f"Cancelamento é livre na etapa de {etapas_abertas[0] if etapas_abertas else 'modelagem'}; "
            "a partir do corte, há custo de tecido já cortado."
        )

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

    # ── Status do pedido ─────────────────────────────────────────
    if intencao == "status_pedido":
        numero = slots.get("numero_pedido")
        df = dados["pedidos"]
        # MÉDIO 29: usa lookup_pedidos pra dar info útil sobre etapas
        etapas = df["etapa"].tolist()
        if numero:
            return (
                f"O pedido {numero} precisa ser consultado pelo setor de logística "
                "em tempo real (eles têm acesso direto à esteira de produção). "
                f"Para sua referência, um pedido passa pelas etapas: {' → '.join(etapas)}. "
                "Alterações só são possíveis na primeira; depois do corte, qualquer mudança "
                "gera retrabalho."
            )
        return (
            "Para verificar a etapa de um pedido, informe o número no formato FF-AAAA-NNNN e fale "
            "com a logística. "
            f"As etapas do processo são: {' → '.join(etapas)}."
        )

    # ── Alterar pedido ───────────────────────────────────────────
    if intencao == "alterar_pedido_especifico":
        numero = slots.get("numero_pedido")
        df = dados["pedidos"]
        etapas_abertas = df[df["pode_alterar"] == "sim"]["etapa"].tolist()
        etapas_fechadas = df[df["pode_alterar"] == "nao"]["etapa"].tolist()
        if numero:
            return (
                f"Para verificar se o pedido {numero} ainda pode ser alterado, "
                "fale com vendas o quanto antes. "
                f"Alterações possíveis na etapa de: {', '.join(etapas_abertas)}. "
                f"Se já estiver em: {', '.join(etapas_fechadas)}, não será viável."
            )
        return (
            f"Alterações em pedidos só rolam enquanto está em: {', '.join(etapas_abertas)}. "
            f"A partir de {etapas_fechadas[0]}, a alteração gera retrabalho e custo. "
            "Informe o número do pedido (FF-AAAA-NNNN) ao setor de vendas."
        )

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
        return (
            f"{personalizacao.title()} em {tecido.replace('_',' ')}: {r['compativel'].upper()}. "
            f"{r['observacao']}"
        )

    # ── Compatibilidade tecido × produto ─────────────────────────
    if intencao == "combinado_tecido_em_produto":
        tecido = slots.get("tecido")
        produto = slots.get("produto")
        df = dados["compat_tecido_produto"]
        filtro = df[(df["tecido"] == tecido) & (df["produto"] == produto)]
        if filtro.empty:
            return f"Não tenho dados sobre {tecido} em {produto}. Consulte o setor técnico."
        r = filtro.iloc[0]
        return (
            f"{tecido.replace('_',' ').title()} em {produto.replace('_',' ')}: "
            f"{r['compativel'].upper()}. {r['observacao']}"
        )

    # ── Cor em tecido ────────────────────────────────────────────
    if intencao == "combinado_cor_em_tecido":
        cor = slots.get("cor")
        tecido = slots.get("tecido")
        df = dados["cor_tecido"]
        filtro = df[(df["tecido"] == tecido) & (df["cor"] == cor)]
        if filtro.empty:
            return f"Não tenho dados sobre a cor {cor} em {tecido}. Consulte o setor de vendas."
        r = filtro.iloc[0]
        disp = "em estoque permanente" if r["disponibilidade"] == "estoque" else "sob demanda (mínimo 80 peças + 7 a 10 dias)"
        return (
            f"{cor.replace('_',' ').title()} em {tecido.replace('_',' ')}: {disp}. "
            f"{r['observacao']}"
        )

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
