from bot.loader import carregar_dados
from bot.extractor import extrair_slots
from bot.classifier import classificar
from bot.responder import responder
from bot.contexto import criar_sessao, resetar_sessao, is_despedida, is_casual

def main():
    print("=" * 50)
    print("  Fashion Flow Bot — Atendimento de Produção")
    print("=" * 50)
    print("Digite sua dúvida ou 'sair' para encerrar.\n")

    dados = carregar_dados()
    sessao = criar_sessao()

    while True:
        try:
            mensagem = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo!")
            break

        if not mensagem:
            continue

        if mensagem.lower() in ("sair", "exit", "quit"):
            print("Bot: Até logo! Qualquer dúvida é só chamar.")
            break

        if is_despedida(mensagem):
            print("Bot: Até logo! Se precisar de mais alguma coisa, estou por aqui.\n")
            sessao = resetar_sessao(sessao)
            continue

        if is_casual(mensagem) and sessao["ativa"]:
            print("Bot: Pode continuar!\n")
            continue

        slots = extrair_slots(mensagem, sessao)
        intencao = classificar(mensagem, slots, dados["intencoes"], sessao)
        resposta = responder(intencao, slots, dados, sessao, mensagem)

        sessao["ativa"] = True
        sessao["ultimo_assunto"] = intencao

        print(f"Bot: {resposta}\n")

if __name__ == "__main__":
    main()
    