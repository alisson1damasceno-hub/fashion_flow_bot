"""
criar.py — CREATE do CRUD de pedidos.

Registra um pedido NOVO no data/pedidos.csv. É chamado quando o cliente termina
de informar, ao longo da conversa, o que quer produzir (produto, quantidade,
cor, tamanho, tecido e personalização).

O que esta operação faz, em ordem:
    1. Confere se chegou toda a informação obrigatória.
    2. Gera um ID novo (FF-AAAA-NNNN).
    3. Define o pedido como recém-nascido: etapa_atual='modelagem',
       status='em_producao'.
    4. Calcula uma previsão simples de término.
    5. Acrescenta a linha no CSV e salva (alteração real no arquivo).

Obs: a COLETA dos dados (perguntar campo por campo) acontece na conversa, no
bot/responder.py. Aqui a gente recebe os dados já reunidos num dicionário.

Pseudocódigo equivalente (Semana 3 do professor — CREATE):

    INÍCIO DO PROCESSO "Criar Novo Pedido"
      RECEBER produto, quantidade, cor, tamanho, tecido, personalizacao
      novo_id = GERAR_ID()
      nova_linha = [novo_id, ..., "modelagem", "em_producao", ...]
      INSERIR nova_linha NA TABELA "pedidos.csv"
      RETORNAR "Pedido registrado! Número: " + novo_id
    FIM DO PROCESSO
"""
from datetime import date, timedelta

from bot.pedidos import persistencia

# Campos que o cliente precisa informar para registrarmos um pedido.
CAMPOS_OBRIGATORIOS = [
    "produto", "quantidade", "cor", "tamanho", "tecido", "personalizacao",
]

# Prazo padrão de produção (em dias) usado para estimar a data_prevista.
# No futuro dá pra puxar isso da lookup_prazo.csv; por ora, um valor simples.
PRAZO_PADRAO_DIAS = 20


def registrar_pedido(dados_pedido):
    """
    Cria um pedido novo a partir dos dados coletados na conversa.

    Parâmetro:
        dados_pedido (dict): produto, quantidade, cor, tamanho, tecido,
                             personalizacao (e, opcionalmente, observacao).

    Retorna um dict padronizado (igual nas quatro operações):
        {"sucesso": bool, "mensagem": str, "pedido": dict | None}
    """
    # 1. Confere se está faltando alguma informação obrigatória.
    faltando = [c for c in CAMPOS_OBRIGATORIOS if not dados_pedido.get(c)]
    if faltando:
        return {
            "sucesso": False,
            "mensagem": "Ainda faltam informações para registrar: "
                        + ", ".join(faltando) + ".",
            "pedido": None,
        }

    df = persistencia.carregar()
    hoje = date.today()

    # 2. Monta a linha nova do pedido.
    novo = {
        "numero_pedido": persistencia.gerar_id(df, hoje.year),  # ID gerado aqui
        "data_criacao": hoje.isoformat(),
        "produto": dados_pedido["produto"],
        "quantidade": str(dados_pedido["quantidade"]),
        "cor": dados_pedido["cor"],
        "tamanho": dados_pedido["tamanho"],
        "tecido": dados_pedido["tecido"],
        "personalizacao": dados_pedido["personalizacao"],
        "etapa_atual": "modelagem",        # todo pedido nasce na modelagem
        "status": "em_producao",
        "data_prevista": (hoje + timedelta(days=PRAZO_PADRAO_DIAS)).isoformat(),
        "observacao": dados_pedido.get("observacao", ""),
    }

    # 3. Acrescenta a linha no fim do DataFrame e salva no arquivo (real).
    df.loc[len(df)] = [novo[coluna] for coluna in persistencia.COLUNAS]
    persistencia.salvar(df)

    # 4. Mensagem amigável de confirmação para o cliente.
    msg = (
        f"Pedido registrado! Seu número é {novo['numero_pedido']}. "
        f"Resumo: {novo['quantidade']} x {novo['produto'].replace('_', ' ')} "
        f"{novo['cor'].replace('_', ' ')}, tamanho {novo['tamanho']}, em "
        f"{novo['tecido'].replace('_', ' ')}, personalização: {novo['personalizacao']}. "
        f"Ele começa na etapa de modelagem; previsão de término na produção: "
        f"{novo['data_prevista']}. Guarde esse número para consultar o andamento."
    )
    return {"sucesso": True, "mensagem": msg, "pedido": novo}
