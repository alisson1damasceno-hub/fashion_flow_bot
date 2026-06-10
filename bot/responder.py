import unicodedata


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def responder(intencao, slots, dados, sessao=None, mensagem=""):

    """
    Recebe a intenção classificada, os slots extraídos e todos os dados.
    Retorna a resposta em texto para o usuário.
    """
# ── Seleção de menu ─────────────────────────────────────────
    if intencao == "selecao_opcao":
        from rapidfuzz import fuzz

        opcao_menu = sessao.get("aguardando_opcao") if sessao else None
        opcoes_por_menu = {
            # ── Qualidade ────────────────────────────────────────
            "menu_qualidade": {
                "originalidade das pecas": "qualidade_originalidade",
                "durabilidade":            "qualidade_durabilidade",
                "controle de qualidade":   "qualidade_controle",
                "defeitos de fabricacao":  "qualidade_defeito",
                "certificacoes":           "qualidade_certificacoes",
            },
            # ── Personalização (raiz) ────────────────────────────
            "menu_personalizacao": {
                "tipos de personalizacao":  "personalizacao_tipos",
                "cores disponiveis":        "personalizacao_cores",
                "tamanhos disponiveis":     "personalizacao_tamanhos",
                "quantidade minima":        "personalizacao_quantidade",
                "prazo de personalizacao":  "personalizacao_prazo",
                "envio de arte":            "personalizacao_envio_arte",
            },
            # ── Tipos de personalização ──────────────────────────
            "menu_personalizacao_tipos": {
                "estampa silkscreen":    "personalizacao_silkscreen",
                "estampa dtf digital":   "personalizacao_dtf",
                "bordado":               "personalizacao_bordado",
                "etiqueta personalizada":"personalizacao_etiqueta",
                "modelagem exclusiva":   "personalizacao_modelagem_exclusiva",
            },
            # ── Cores (personalização) ───────────────────────────
            "menu_personalizacao_cores": {
                "cores basicas em estoque":       "cores_basicas",
                "tingimento sob demanda":         "cores_sob_demanda",
                "combinacao cor peca estampa":    "cores_combinacao",
                "limite de cores por tecnica":    "cores_limite_tecnica",
            },
            # ── Tamanhos (personalização) ────────────────────────
            "menu_personalizacao_tamanhos": {
                "grade adulto":       "tamanhos_adulto",
                "grade infantil":     "tamanhos_infantil",
                "plus size":          "tamanhos_plus_size",
                "tabela de medidas":  "tamanhos_tabela_medidas",
            },
            # ── Quantidade mínima ────────────────────────────────
            "menu_personalizacao_quantidade": {
                "minimo por tipo de personalizacao": "qtd_minima_personalizacao",
                "minimo por cor":                    "qtd_minima_cor",
                "pedidos grandes 500":               "qtd_grande_volume",
                "pedidos pequenos ate 30":           "qtd_pequena_volume",
            },
            # ── Sustentabilidade ─────────────────────────────────
            "menu_sustentabilidade": {
                "aproveitamento de tecido":  "sustent_aproveitamento",
                "materiais sustentaveis":    "sustent_materiais_eco",
                "reciclagem de sobras":      "sustent_reciclagem",
                "tinturas e quimicos":       "sustent_quimicos",
                "praticas trabalhistas":     "sustent_trabalho",
                "logistica sustentavel":     "sustent_logistica",
            },
            # ── Manutenção ───────────────────────────────────────
            "menu_manutencao": {
                "como lavar":        "manut_lavar",
                "ferro de passar":   "manut_ferro",
                "secadora":          "manut_secadora",
                "alvejante":         "manut_alvejante",
                "tirar mancha":      "manut_mancha",
                "cuidados por tecido":"manut_por_tecido",
                "encolhimento":      "manut_encolhimento",
                "desbotamento":      "manut_desbotamento",
            },
            # ── Cuidados por tecido ──────────────────────────────
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
            # ── Produção ─────────────────────────────────────────
            "menu_producao": {
                "etapas do processo":    "producao_etapas",
                "onde e produzido":      "producao_onde",
                "capacidade produtiva":  "producao_capacidade",
                "tecnologia":            "producao_tecnologia",
                "equipe":                "producao_equipe",
                "modelagem":             "producao_modelagem",
                "corte e costura":       "producao_corte_costura",
            },
            # ── Catálogo ─────────────────────────────────────────
            "menu_catalogo": {
                "camisetas e basicas":      "cat_camisetas",
                "moletons e jaquetas":      "cat_moletons",
                "calcas e shorts":          "cat_calcas",
                "vestidos":                 "cat_vestidos",
                "uniformes corporativos":   "cat_uniformes",
                "linha infantil":           "cat_infantil",
            },
            # ── Sugestão de produto ──────────────────────────────
            "menu_sugestao_produto": {
                "casual dia a dia":         "sug_casual",
                "trabalho corporativo":     "sug_trabalho",
                "esporte academia":         "sug_esporte",
                "festa ocasiao especial":   "sug_festa",
                "inverno":                  "sug_inverno",
                "verao":                    "sug_verao",
                "uniforme empresa":         "sug_uniforme",
                "presente":                 "sug_presente",
            },
            # ── Tecidos ──────────────────────────────────────────
            "menu_tecidos": {
                "lista de tecidos disponiveis": "tec_disponiveis",
                "composicao de cada peca":      "tec_composicao",
                "origem dos tecidos":           "tec_origem",
                "sugestao por uso":             "sug_tecido_uso",
                "tecido para pele sensivel":    "tec_pele_sensivel",
                "nao trabalhamos com":          "tec_couro",
            },
            # ── Sugestão de tecido por uso ───────────────────────
            "menu_sug_tecido_uso": {
                "clima quente":   "sug_tec_quente",
                "clima frio":     "sug_tec_frio",
                "uso diario":     "sug_tec_diario",
                "esporte":        "sug_tec_esporte",
                "ocasiao formal": "sug_tec_formal",
            },
            # ── Prazos ───────────────────────────────────────────
            "menu_previsao_prazo": {
                "prazo padrao":          "prazo_padrao",
                "com personalizacao":    "prazo_com_personalizacao",
                "pedido urgente":        "prazo_urgente",
                "pedido grande 500":     "prazo_grande_pedido",
                "atraso de pedido":      "prazo_atraso",
            },
            # ── Etapas do pedido ─────────────────────────────────
            "menu_etapas_pedido": {
                "em que etapa esta":         "etapa_consulta",
                "alterar pedido":            "alterar_pedido",
                "cancelar pedido":           "cancelar_pedido",
                "acompanhamento detalhado":  "acompanhamento",
            },
        }

        opcoes = opcoes_por_menu.get(opcao_menu, {})

        # usuário digitou um número (ex: "2")
        try:
            numero = int(mensagem.strip())
            lista = list(opcoes.values())
            if 1 <= numero <= len(lista):
                escolha = lista[numero - 1]
                if sessao:
                    sessao["slots_acumulados"][opcao_menu.replace("menu_", "")] = escolha
                    sessao["aguardando_opcao"] = None
                df_int = dados["intencoes"]
                row_sub = df_int[df_int["id_intencao"] == escolha]
                if not row_sub.empty:
                    return row_sub.iloc[0]["resposta_padrao"]
                return f"Entendido! Registrei: {escolha.replace('_', ' ')}. Como posso continuar te ajudando?"
        except (ValueError, TypeError):
            pass

        # usuário digitou o nome (ex: "bordado")
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
                sessao["slots_acumulados"][opcao_menu.replace("menu_", "")] = melhor_valor
                sessao["aguardando_opcao"] = None
            # busca resposta direta no CSV para menus de subtópico
            df_int = dados["intencoes"]
            row_sub = df_int[df_int["id_intencao"] == melhor_valor]
            if not row_sub.empty:
                return row_sub.iloc[0]["resposta_padrao"]
            return f"Entendido! Registrei: {melhor_valor.replace('_', ' ')}. Como posso continuar te ajudando?"

        # não entendeu — mostra o menu de novo
        lista_opcoes = "\n".join(f"  {i+1}. {c.title()}" for i, c in enumerate(opcoes.keys()))
        return f"Não entendi sua escolha. Por favor, selecione uma opção:\n{lista_opcoes}"


    # ── Status do pedido ─────────────────────────────────────────
    if intencao == "status_pedido":
        numero = slots.get("numero_pedido")
        if numero:
            return (
                f"Para consultar o status do pedido {numero}, "
                "entre em contato com o setor de logística informando esse número. "
                "Eles têm acesso em tempo real a todas as etapas da produção."
            )
        df = dados["pedidos"]
        etapa = slots.get("etapa_mencionada")
        if etapa:
            row = df[normalizar(df["etapa"]) == normalizar(etapa)]
            if not row.empty:
                r = row.iloc[0]
                pode = "ainda é possível fazer alterações" if r["pode_alterar"] == "sim" else "não é mais possível fazer alterações"
                return (
                    f"Na etapa de {r['etapa']}: {r['descricao']} "
                    f"Nesse momento, {pode}. {r['observacao']}"
                )
        return (
            "Para verificar em qual etapa está seu pedido, entre em contato "
            "com o setor de logística informando o número do pedido (formato FF-AAAA-NNNN). "
            "As etapas do nosso processo são: modelagem → corte → costura → "
            "personalização → qualidade → embalagem e expedição."
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
                "entre em contato com o setor de vendas o quanto antes. "
                f"Alterações só são possíveis na etapa de: {', '.join(etapas_abertas)}. "
                f"Se já estiver em: {', '.join(etapas_fechadas)}, não será mais viável."
            )
        return (
            f"Alterações em pedidos só são possíveis enquanto está na etapa de: "
            f"{', '.join(etapas_abertas)}. "
            f"A partir de {etapas_fechadas[0]}, nenhuma alteração é viável sem gerar "
            "retrabalho e custo adicional. "
            "Informe o número do pedido ao setor de vendas para verificar."
        )

    # ── Viabilidade de produção ──────────────────────────────────
    if intencao == "viabilidade_producao":
        quantidade = slots.get("quantidade", 0)
        tecido = slots.get("tecido")
        prazo = slots.get("prazo_desejado")

        df_cap = dados["capacidade_produtiva"]
        df_est = dados["estoque_materiais"]

        costura = df_cap[df_cap["setor"] == "costura"].iloc[0]
        cap_disponivel = int(costura["disponivel_hoje_pecas"])
        viavel_capacidade = quantidade <= cap_disponivel

        material_ok = True
        material_msg = ""
        if tecido:
            row_mat = df_est[df_est["tecido"] == tecido]
            if not row_mat.empty:
                r = row_mat.iloc[0]
                material_ok = r["status"] == "disponivel"
                if not material_ok:
                    material_msg = (
                        f" Porém, {tecido.replace('_', ' ')} está sem estoque no momento"
                        f" — reposição prevista para {r['previsao_reposicao']}."
                    )
                else:
                    material_msg = (
                        f" {tecido.replace('_', ' ').title()} disponível "
                        f"({r['metros_disponivel']}m em estoque)."
                    )

        if prazo and prazo < 15:
            return (
                f"Para {quantidade} peças em {prazo} dias: nosso prazo mínimo de produção "
                "é de 15 dias úteis para pedidos sem personalização. "
                f"A capacidade atual do setor de costura comporta {cap_disponivel} peças/dia.{material_msg} "
                "Para prazos urgentes, entre em contato com vendas — aplicamos taxa de urgência de 20% a 40%."
            )

        if viavel_capacidade and material_ok:
            return (
                f"Sim, temos capacidade técnica para produzir {quantidade} peças. "
                f"O setor de costura tem {cap_disponivel} peças disponíveis hoje.{material_msg} "
                "Para confirmar e iniciar o pedido, entre em contato com o setor de vendas."
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
                f"Pode haver dificuldades para produzir {quantidade} peças agora: "
                f"{'; '.join(motivos)}. "
                "Entre em contato com vendas para avaliar alternativas."
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
                f"Não tenho dados de consumo de tecido para {produto or 'esse produto'}. "
                "Entre em contato com o setor técnico para uma análise precisa."
            )

        metros_por_peca = float(filtro.iloc[0]["metros_por_peca"])
        metros_necessarios = round(metros_por_peca * quantidade, 2)
        obs = filtro.iloc[0]["observacao"]

        if metragem > 0:
            if metragem >= metros_necessarios:
                sobra = round(metragem - metros_necessarios, 2)
                return (
                    f"Para {quantidade} peças de {produto.replace('_', ' ')}, "
                    f"são necessários {metros_necessarios}m de tecido "
                    f"({metros_por_peca}m por peça). "
                    f"Com {metragem}m você tem o suficiente — sobram {sobra}m. "
                    f"Obs: {obs}"
                )
            else:
                falta = round(metros_necessarios - metragem, 2)
                return (
                    f"Para {quantidade} peças de {produto.replace('_', ' ')}, "
                    f"são necessários {metros_necessarios}m de tecido "
                    f"({metros_por_peca}m por peça). "
                    f"Com apenas {metragem}m não é suficiente — faltam {falta}m. "
                    f"Obs: {obs}"
                )

        return (
            f"Para {quantidade} peças de {produto.replace('_', ' ')}, "
            f"são necessários aproximadamente {metros_necessarios}m de tecido "
            f"({metros_por_peca}m por peça). "
            f"Obs: {obs}"
        )

    # ── Prazo ────────────────────────────────────────────────────
    if intencao == "combinado_prazo_qtd_produto":
        quantidade = slots.get("quantidade", 0)
        produto = slots.get("produto")
        personalizacao = slots.get("personalizacao", "nenhuma")

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
            return (
                f"Não encontrei dados de prazo para {produto} com quantidade {quantidade}. "
                "Entre em contato com o setor de vendas para uma estimativa personalizada."
            )
        r = filtro.iloc[0]
        pers_txt = f" com {personalizacao}" if personalizacao != "nenhuma" else ""
        return (
            f"Para {quantidade} peças de {produto.replace('_', ' ')}{pers_txt}: "
            f"prazo estimado de {r['prazo_min_dias']} a {r['prazo_max_dias']} dias úteis. "
            "Prazo confirmado pelo setor de vendas no fechamento do pedido."
        )

    # ── Preço ────────────────────────────────────────────────────
    if intencao == "combinado_preco_qtd_produto":
        quantidade = slots.get("quantidade", 0)
        produto = slots.get("produto")
        personalizacao = slots.get("personalizacao", "nenhuma")

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
            return (
                f"Não encontrei dados de preço para {produto} com quantidade {quantidade}. "
                "Entre em contato com o setor de vendas para um orçamento personalizado."
            )
        r = filtro.iloc[0]
        total = round(float(r["preco_unitario_estimado"]) * quantidade, 2)
        pers_txt = f" com {personalizacao}" if personalizacao != "nenhuma" else ""
        return (
            f"Para {quantidade} peças de {produto.replace('_', ' ')}{pers_txt}: "
            f"valor unitário estimado de R$ {r['preco_unitario_estimado']} "
            f"({r['desconto_aplicado']} de desconto). "
            f"Total estimado: R$ {total:.2f}. "
            "Valor indicativo — fechamento com o setor de vendas."
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
            f"{personalizacao.title()} em {tecido.replace('_', ' ')}: {r['compativel'].upper()}. "
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
            f"{tecido.replace('_', ' ').title()} em {produto.replace('_', ' ')}: "
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
        disp = "em estoque permanente" if r["disponibilidade"] == "estoque" else "sob demanda (mínimo 80 peças + 7 a 10 dias adicionais)"
        return (
            f"{cor.replace('_', ' ').title()} em {tecido.replace('_', ' ')}: {disp}. "
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
            f"Gramatura recomendada para {produto.replace('_', ' ')} "
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
            f"Grade {grade.replace('_', ' ')} para {produto.replace('_', ' ')}: {disp}. "
            f"{r['observacao']}"
        )

    # ── Resposta padrão do CSV ───────────────────────────────────
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
        "gramatura, tamanhos e status de pedidos. "
        "Pode reformular?"
    )