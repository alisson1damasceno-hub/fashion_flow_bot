import gradio as gr

from bot.loader import carregar_dados
from bot.classifier import classificar
from bot.extractor import extrair_slots
from bot.responder import responder

dados = carregar_dados()

sessao = {
    "ativa": False,
    "ultimo_assunto": None,
    "slots_acumulados": {},
}

def chat(mensagem, historico):
    slots    = extrair_slots(mensagem, sessao)
    intencao = classificar(mensagem, slots, dados["intencoes"], sessao)
    resposta = responder(intencao, slots, dados, sessao, mensagem)
    sessao["ativa"]          = True
    sessao["ultimo_assunto"] = intencao
    return resposta

theme = gr.themes.Soft(
    primary_hue="pink",
    secondary_hue="rose",
    neutral_hue="slate",
)

css = """
footer { display: none !important; }
"""

with gr.Blocks(title="Fashion Flow Bot", theme=theme, css=css, fill_width=True) as demo:

    gr.ChatInterface(
        fn=chat,
        chatbot=gr.Chatbot(
            placeholder="<strong>Bem-vindo a Fashion Flow!</strong><br>Como posso te ajudar hoje?",
            avatar_images=(None, "https://cdn-icons-png.flaticon.com/512/4712/4712035.png"),
            height=600,
        ),
        textbox=gr.Textbox(
            placeholder="Digite sua mensagem...",
            container=False,
            scale=7,
        ),
        examples=[
            "Quais tecidos vocês usam?",
            "Qual o prazo de entrega?",
            "Quais são os tamanhos?",
            "Cuidados com a camisa",
        ],
    )

if __name__ == "__main__":
    demo.launch()