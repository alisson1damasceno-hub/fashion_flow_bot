"""
consultar.py — READ do CRUD de pedidos.

Encontra um pedido pelo ID que o cliente mandou e devolve o andamento dele.

Regra de setor: como somos o bot da PRODUÇÃO, o status que entregamos é a etapa
de fabricação (modelagem → corte → costura → personalizacao → qualidade →
embalagem_expedicao). Status de ENTREGA/transporte continua sendo da logística —
por isso a resposta avisa isso no final.

Pseudocódigo equivalente (Semana 3 — READ, com o SE/SENÃO do "erro 404"):

    INÍCIO DO PROCESSO "Consultar Pedido"
      RECEBER numero_pedido
      linha = BUSCAR NA TABELA "pedidos.csv" ONDE numero_pedido É IGUAL A ...
      SE linha É VAZIO ENTÃO:
        RETORNAR "Não encontrei o pedido."   # plano B obrigatório
      SENÃO:
        RETORNAR "Etapa atual de fabricação: " + linha[etapa_atual]
      FIM SE
    FIM DO PROCESSO
"""
from bot.pedidos import persistencia


def _info_etapa(etapa):
    """Devolve a linha da etapa (pode_alterar, descricao, observacao)."""
    df = persistencia.carregar_etapas()
    linha = df[df["etapa"] == etapa]
    if linha.empty:
        return {"pode_alterar": "nao", "descricao": "", "observacao": ""}
    return linha.iloc[0].to_dict()


def consultar_pedido(numero, nome_cliente=None):
    """
    Consulta um pedido pelo ID.

    Retorna o dict padrão:
        {"sucesso": bool, "mensagem": str, "pedido": dict | None}

    - achou      → sucesso=True, mensagem com produto/quantidade/etapa/previsão.
    - não achou  → sucesso=False, mensagem pedindo pra conferir o número.
    """
    df, indice, linha = persistencia.buscar_por_id(numero)

    if linha is None:
        return {
            "sucesso": False,
            "mensagem": f"Não encontrei o pedido {numero}. Confere o número? "
                        "O formato é FF-AAAA-NNNN, por exemplo FF-2026-0001.",
            "pedido": None,
        }

    # Trava de dono: só mostra o pedido se ele for desse cliente.
    if not persistencia.e_dono(linha, nome_cliente):
        return {
            "sucesso": False,
            "mensagem": f"O pedido {numero} não está no seu nome. Confere o número?",
            "pedido": None,
        }

    etapa = linha["etapa_atual"]
    info = _info_etapa(etapa)
    pode_alterar = info.get("pode_alterar", "nao") == "sim"

    # Monta a frase do "situação" conforme o status macro do pedido.
    if linha["status"] == "cancelado":
        situacao = "Esse pedido está CANCELADO."
    elif linha["status"] == "concluido":
        situacao = "Esse pedido já está CONCLUÍDO na produção (embalado e pronto)."
    else:
        situacao = f"Etapa atual de fabricação: {etapa.replace('_', ' ')}."

    # Só falamos de "alterar" se o pedido ainda está em produção. Cancelado ou
    # concluído não cabe dizer "ainda dá pra alterar".
    if linha["status"] in ("cancelado", "concluido"):
        alteravel = ""
    elif pode_alterar:
        alteravel = "Ainda dá pra alterar (está na modelagem)."
    else:
        alteravel = "Nesta etapa não dá mais pra alterar."

    msg = (
        f"Pedido {linha['numero_pedido']}: {linha['quantidade']} x "
        f"{linha['produto'].replace('_', ' ')} {linha['cor'].replace('_', ' ')}, "
        f"tamanho {linha['tamanho']}. {situacao} "
        f"Previsão de término na produção: {linha['data_prevista']}."
        f"{(' ' + alteravel) if alteravel else ''} "
        "(O status de entrega quem informa é a logística.)"
    )
    return {"sucesso": True, "mensagem": msg, "pedido": linha}
