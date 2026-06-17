"""
cancelar.py — DELETE do CRUD de pedidos.

Aqui usamos "delete suave" (soft delete): em vez de APAGAR a linha do CSV, a
gente marca status='cancelado'. Assim o histórico do pedido continua existindo.

Por que não apagar de vez?
    - Numa fábrica, sumir com um pedido é perigoso (perde rastro, relatório...).
    - Numa demo, é mais seguro: nada some do arquivo por acidente.
    - Dá pra mostrar o pedido cancelado depois, se precisar.

Pseudocódigo equivalente (Semana 3 — SOFT DELETE, que é tecnicamente um UPDATE):

    INÍCIO DO PROCESSO "Cancelar Pedido"
      RECEBER numero_pedido
      linha = BUSCAR NA TABELA "pedidos.csv" ONDE numero_pedido É IGUAL A ...
      SE linha EXISTE ENTÃO:
        linha[status] = "cancelado"      # só muda o status, NÃO apaga a linha!
        linha[observacao] = motivo
        SALVAR TABELA "pedidos.csv"
        RETORNAR "Pedido cancelado. Histórico mantido."
      FIM SE
    FIM DO PROCESSO
"""
from bot.pedidos import persistencia


def cancelar_pedido(numero, motivo=""):
    """
    Cancela um pedido (soft delete: status vira 'cancelado').

    Retorna {"sucesso": bool, "mensagem": str, "pedido": dict | None}.
    """
    df, indice, linha = persistencia.buscar_por_id(numero)

    # 1. O pedido existe?
    if linha is None:
        return {
            "sucesso": False,
            "mensagem": f"Não encontrei o pedido {numero}. Confere o número?",
            "pedido": None,
        }

    # 2. Já está cancelado?
    if linha["status"] == "cancelado":
        return {
            "sucesso": False,
            "mensagem": f"O pedido {numero} já estava cancelado.",
            "pedido": linha,
        }

    # 3. Já foi concluído? (não cancela produção pronta por aqui)
    if linha["status"] == "concluido":
        return {
            "sucesso": False,
            "mensagem": f"O pedido {numero} já foi concluído na produção, não dá pra "
                        "cancelar por aqui — fale com o setor de vendas.",
            "pedido": linha,
        }

    # 4. Marca como cancelado e salva no arquivo (real).
    df.loc[indice, "status"] = "cancelado"
    if motivo:
        df.loc[indice, "observacao"] = f"cancelado: {motivo}"
    persistencia.salvar(df)

    return {
        "sucesso": True,
        "mensagem": f"Pedido {numero} cancelado. (Ele continua no histórico, marcado "
                    "como cancelado, mas sai da produção.)",
        "pedido": df.loc[indice].to_dict(),
    }
