from bot.loader import carregar_dados
from bot.extractor import extrair_slots
from bot.classifier import classificar
from bot.responder import responder

def main():
    print("=" * 50)
    print("  Fashion Flow Bot — Atendimento de Produção")
    print("=" * 50)
    print("Digite sua dúvida ou 'sair' para encerrar.\n")

    dados = carregar_dados()

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

        slots = extrair_slots(mensagem)
        intencao = classificar(mensagem, slots, dados["intencoes"])
        resposta = responder(intencao, slots, dados)

        print(f"Bot: {resposta}\n")

if __name__ == "__main__":
    main()
    