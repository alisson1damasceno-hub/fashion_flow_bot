"""
Interface web do Fashion Flow Bot (Gradio).

CRÍTICO 7: cada conversa tem sua própria sessão via gr.State() — não há
mais variável global compartilhada entre usuários.
"""
import gradio as gr

from bot.loader import carregar_dados
from bot.extractor import extrair_slots
from bot.classifier import classificar
from bot.responder import responder
from bot.contexto import (
    criar_sessao, resetar_sessao,
    is_despedida, is_casual,
    merge_com_contexto, atualizar_sessao_pos_turno,
)


dados = carregar_dados()


def processar(mensagem, sessao):
    """Pipeline completo para um turno. Retorna (resposta, sessao_atualizada)."""
    if sessao is None:
        sessao = criar_sessao()

    mensagem = (mensagem or "").strip()
    if not mensagem:
        return "", sessao

    if is_despedida(mensagem):
        sessao = resetar_sessao(sessao)
        return "Até logo! Se precisar, é só voltar.", sessao

    if is_casual(mensagem) and sessao["ativa"]:
        return "Beleza, pode continuar!", sessao

    em_menu = bool(sessao.get("aguardando_opcao"))
    slots_turno = extrair_slots(mensagem, em_menu=em_menu)
    slots_efetivos = merge_com_contexto(slots_turno, sessao)
    intencao = classificar(mensagem, slots_turno, slots_efetivos, dados["intencoes"], sessao)
    resposta = responder(intencao, slots_efetivos, dados, sessao, mensagem)
    atualizar_sessao_pos_turno(sessao, mensagem, slots_efetivos, intencao, resposta)
    return resposta, sessao


def memoria_str(sessao):
    """Representação amigável do contexto para exibição."""
    if not sessao:
        return "_(sessão vazia)_"
    foco = sessao.get("foco_atual") or {}
    hist = sessao.get("historico_turnos") or []
    foco_md = (
        "**Foco atual:** "
        + (", ".join(f"`{k}`={v}" for k, v in foco.items()) if foco else "_(vazio)_")
    )
    ultimos = hist[-3:]
    hist_md = ""
    if ultimos:
        linhas = [f"{i+1}. _{t['msg']}_ → `{t['intencao']}`" for i, t in enumerate(ultimos)]
        hist_md = "\n\n**Últimos turnos:**\n" + "\n".join(linhas)
    return foco_md + hist_md


def chat_fn(mensagem, historico, sessao):
    """Handler do Gradio ChatInterface."""
    resposta, sessao_nova = processar(mensagem, sessao)
    return resposta, sessao_nova, memoria_str(sessao_nova)


def limpar(sessao):
    """Reseta a sessão (botão limpar)."""
    nova = criar_sessao()
    return nova, memoria_str(nova)


theme = gr.themes.Soft(
    primary_hue="emerald",
    secondary_hue="amber",
    neutral_hue="slate",
)

css = """
footer { display: none !important; }
.gradio-container { max-width: 1100px !important; }
"""

with gr.Blocks(title="Fashion Flow Bot") as demo:
    gr.Markdown(
        "# 🧵 Fashion Flow — Atendimento de Produção\n"
        "_Tire dúvidas sobre prazos, preços, tecidos, personalização e pedidos._"
    )

    sessao_state = gr.State(value=None)

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                placeholder=(
                    "<strong>Bem-vinda à Fashion Flow!</strong><br>"
                    "Pode falar sobre preço, prazo, tecido, personalização. "
                    "Tente: <em>preço de 100 polos com bordado</em>"
                ),
                height=520,
            )
            with gr.Row():
                msg = gr.Textbox(
                    placeholder="Digite sua mensagem...",
                    container=False,
                    scale=7,
                )
                btn_enviar = gr.Button("Enviar", variant="primary", scale=1)
            with gr.Row():
                btn_limpar = gr.Button("🗑️ Limpar conversa", size="sm")
            gr.Examples(
                examples=[
                    "preço de 100 polos com bordado",
                    "consigo produzir 500 peças em 10 dias?",
                    "meu pedido FF-2025-0001 está em qual etapa?",
                    "qual o prazo de 30 vestidos?",
                    "tem algodão em estoque?",
                ],
                inputs=msg,
            )

        with gr.Column(scale=1):
            gr.Markdown("### 🧠 Memória da conversa")
            memoria_box = gr.Markdown("_(vazio)_")

    def responder_e_atualizar(mensagem, historico, sessao):
        if not mensagem.strip():
            return historico, sessao, memoria_str(sessao), ""
        resp, sessao_nova = processar(mensagem, sessao)
        historico = historico or []
        historico.append({"role": "user", "content": mensagem})
        historico.append({"role": "assistant", "content": resp})
        return historico, sessao_nova, memoria_str(sessao_nova), ""

    btn_enviar.click(
        responder_e_atualizar,
        inputs=[msg, chatbot, sessao_state],
        outputs=[chatbot, sessao_state, memoria_box, msg],
    )
    msg.submit(
        responder_e_atualizar,
        inputs=[msg, chatbot, sessao_state],
        outputs=[chatbot, sessao_state, memoria_box, msg],
    )
    btn_limpar.click(
        lambda: ([], criar_sessao(), memoria_str(criar_sessao())),
        outputs=[chatbot, sessao_state, memoria_box],
    )


if __name__ == "__main__":
    demo.launch(theme=theme, css=css)
