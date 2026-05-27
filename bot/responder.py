import unicodedata


def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def responder(intencao, slots, dados):
    """
    Recebe a intenção classificada, os slots extraídos e todos os dados.
    Retorna a resposta em texto para o usuário.
    """

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
        corte = df_cap[df_cap["setor"] == "corte"].iloc[0]

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
            f"{r['observacao']}. "
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

    # ── Resposta padrão do CSV (intenções diretas e guiadas) ─────
    df_int = dados["intencoes"]
    row = df_int[df_int["id_intencao"] == intencao]
    if not row.empty:
        resposta = row.iloc[0]["resposta_padrao"]
        followup = row.iloc[0]["pergunta_followup"]
        if followup and str(followup) != "nan":
            return f"{resposta}\n{followup}"
        return resposta

    # ── Fallback ─────────────────────────────────────────────────
    return (
        "Não entendi bem sua pergunta. Posso ajudar com: "
        "prazos, preços, tecidos, personalização, compatibilidade, "
        "gramatura, tamanhos e status de pedidos. "
        "Pode reformular?"
    )
