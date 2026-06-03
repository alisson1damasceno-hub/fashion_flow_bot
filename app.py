from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bot.loader import carregar_dados
from bot.extractor import extrair_slots
from bot.classifier import classificar
from bot.responder import responder
from bot.contexto import criar_sessao, resetar_sessao, is_despedida, is_casual

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# dados carregados uma vez na inicialização
dados = carregar_dados()

# sessões em memória — cada sessao_id tem seu próprio contexto
sessoes = {}

class MensagemRequest(BaseModel):
    sessao_id: str
    mensagem: str

@app.post("/chat")
def chat(req: MensagemRequest):
    sessao_id = req.sessao_id
    mensagem = req.mensagem.strip()

    # cria sessão se não existir
    if sessao_id not in sessoes:
        sessoes[sessao_id] = criar_sessao()

    sessao = sessoes[sessao_id]

    if not mensagem:
        return {"resposta": ""}

    if is_despedida(mensagem):
        sessoes[sessao_id] = resetar_sessao(sessao)
        return {"resposta": "Até logo! Se precisar de mais alguma coisa, estou por aqui."}

    if is_casual(mensagem) and sessao["ativa"]:
        return {"resposta": "Pode continuar!"}

    slots = extrair_slots(mensagem, sessao)
    intencao = classificar(mensagem, slots, dados["intencoes"], sessao)
    resposta_texto = responder(intencao, slots, dados, sessao, mensagem)

    sessao["ativa"] = True
    sessao["ultimo_assunto"] = intencao

    return {"resposta": resposta_texto}

@app.get("/")
def root():
    return {"status": "Fashion Flow Bot online"}