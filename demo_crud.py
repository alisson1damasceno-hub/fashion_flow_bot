"""
demo_crud.py — Demonstração do CRUD de pedidos acontecendo NA CONVERSA.

Roda uma conversa simulada pelo mesmo pipeline do bot (extrair_slots →
classificar → responder) e mostra o data/pedidos.csv ANTES e DEPOIS, provando
que as requisições do cliente alteram o CSV de verdade.

Execute: python demo_crud.py
"""
from pathlib import Path

from bot.loader import carregar_dados
from bot.extractor import extrair_slots
from bot.classifier import classificar
from bot.responder import responder
from bot.contexto import criar_sessao, merge_com_contexto, atualizar_sessao_pos_turno

CSV = Path(__file__).parent / "data" / "pedidos.csv"

# Estado inicial conhecido. A demo reseta o pedidos.csv para isto no começo,
# pra poder rodar quantas vezes quiser sempre a partir do mesmo ponto.
SEED = """numero_pedido,data_criacao,produto,quantidade,cor,tamanho,tecido,personalizacao,etapa_atual,status,data_prevista,observacao
FF-2026-0001,2026-06-01,camiseta_basica,150,preto,M,algodao_pima,bordado,corte,em_producao,2026-07-06,uniforme PJ
FF-2026-0002,2026-06-10,moletom,80,marinho,G,moletom_flanelado,silkscreen,modelagem,em_producao,2026-07-15,ainda em modelagem
FF-2026-0003,2026-05-28,polo,200,branco,GG,algodao_penteado,bordado,costura,em_producao,2026-07-02,uniforme corporativo
FF-2026-0004,2026-06-05,vestido_midi,30,vinho,P,viscose,nenhuma,qualidade,em_producao,2026-06-22,sem personalizacao
FF-2026-0005,2026-05-20,legging,120,preto,M,suplex,dtf,embalagem_expedicao,concluido,2026-06-12,pronto para envio
"""


def resetar_seed():
    """Volta o pedidos.csv pro estado inicial, pra demo ser repetível."""
    CSV.write_text(SEED, encoding="utf-8")


def mostrar_csv(titulo):
    print(f"\n===== {titulo} =====")
    print(CSV.read_text(encoding="utf-8").strip())
    print("=" * (12 + len(titulo)))


def conversa(mensagens):
    """Roda uma lista de mensagens numa única sessão (como uma conversa real)."""
    dados = carregar_dados()
    sessao = criar_sessao()
    for msg in mensagens:
        em_menu = bool(sessao.get("aguardando_opcao"))
        slots_turno = extrair_slots(msg, em_menu=em_menu)
        slots_efetivos = merge_com_contexto(slots_turno, sessao)
        intencao = classificar(msg, slots_turno, slots_efetivos, dados["intencoes"], sessao)
        resposta = responder(intencao, slots_efetivos, dados, sessao, msg)
        atualizar_sessao_pos_turno(sessao, msg, slots_efetivos, intencao, resposta)
        print(f"\nVocê: {msg}")
        print(f"Bot [{intencao}]: {resposta}")


resetar_seed()
mostrar_csv("pedidos.csv ANTES")

print("\n\n########## R — CONSULTAR um pedido que existe ##########")
conversa(["qual o status do pedido FF-2026-0001"])

print("\n\n########## R — CONSULTAR pedindo o ID no meio da conversa ##########")
conversa(["status do pedido", "FF-2026-0003"])

print("\n\n########## C — REGISTRAR um pedido novo (coleta na conversa) ##########")
conversa([
    "quero fazer um pedido",
    "camiseta",
    "100",
    "branco",
    "G",
    "algodao pima",
    "bordado",
])

print("\n\n########## U — ALTERAR (permitido: pedido novo está na modelagem) ##########")
conversa(["mudar a cor do pedido FF-2026-0006 para preto"])

print("\n\n########## U — AVANÇAR ETAPA (operação-assinatura da Produção, Semana 3) ##########")
conversa(["avançar a etapa do pedido FF-2026-0006", "status do pedido FF-2026-0006"])

print("\n\n########## U — ALTERAR (bloqueado: FF-2026-0001 já está no corte) ##########")
conversa(["quero mudar a cor do pedido FF-2026-0001 para branco"])

print("\n\n########## D — CANCELAR um pedido (soft delete) ##########")
conversa(["quero cancelar o pedido FF-2026-0002"])

print("\n\n########## R — CONSULTAR o que foi cancelado ##########")
conversa(["status do pedido FF-2026-0002"])

mostrar_csv("pedidos.csv DEPOIS")
