import re
import unicodedata

def normalizar(texto):
    """Remove acentos e converte para minúsculas."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto

def extrair_slots(mensagem):
    """
    Recebe a mensagem do usuário e retorna um dicionário
    com os slots identificados.
    """
    t = normalizar(mensagem)
    slots = {}

    # ── quantidade ──────────────────────────────────────────────
    match = re.search(r'\b(\d+)\s*(pecas?|camisetas?|polos?|moletons?|uniformes?|vestidos?|calcas?|bermudas?|unidades?|un|pcs)?\b', t)
    if match:
        slots["quantidade"] = int(match.group(1))

    # ── produto ──────────────────────────────────────────────────
    produtos = {
    "camiseta de time":       "camiseta_basica",
    "camisa":                 "camiseta_basica",
    "camiseta basica":        "camiseta_basica",
    "camiseta premium":       "camiseta_premium",
    "baby look":              "baby_look",
    "camiseta":               "camiseta_basica",
    "polo":                   "polo",
    "moletom":                "moletom",
    "jaqueta":                "jaqueta",
    "calca jeans":            "calca_jeans",
    "calca alfaiataria":      "calca_alfaiataria",
    "legging":                "legging",
    "bermuda":                "bermuda",
    "regata":                 "regata",
    "vestido midi":           "vestido_midi",
    "vestido longo":          "vestido_longo",
    "jogger":                 "jogger",
    "uniforme polo":          "uniforme_polo",
    "uniforme jaleco":        "uniforme_jaleco",
    "uniforme":               "uniforme_polo",
    "oversized":              "oversized",
    "jaleco":                 "uniforme_jaleco",
}
    for chave, valor in produtos.items():
        if normalizar(chave) in t:
            slots["produto"] = valor
            break

    # ── personalização ───────────────────────────────────────────
    personalizacoes = {
        "silkscreen": "silkscreen",
        "silk":       "silkscreen",
        "serigrafia": "silkscreen",
        "dtf":        "dtf",
        "bordado":    "bordado",
        "bordada":    "bordado",
        "etiqueta":   "etiqueta",
    }
    for chave, valor in personalizacoes.items():
        if chave in t:
            slots["personalizacao"] = valor
            break

    # ── tecido ───────────────────────────────────────────────────
    tecidos = {
        "algodao pima":        "algodao_pima",
        "algodao penteado":    "algodao_penteado",
        "algodao basico":      "algodao_basico",
        "dry.?fit":            "dry_fit",
        "dry fit":             "dry_fit",
        "malha mista":         "malha_mista",
        "moletom flanelado":   "moletom_flanelado",
        "moletom peluciado":   "moletom_peluciado",
        "viscose":             "viscose",
        "linho":               "linho",
        "suplex":              "suplex",
        "jeans":               "jeans",
        "alfaiataria":         "alfaiataria",
        "la":                  "la",
        "tencel":              "tencel",
        "algodao":             "algodao_basico",
    }
    for chave, valor in tecidos.items():
        if re.search(chave, t):
            slots["tecido"] = valor
            break

    # ── cor ──────────────────────────────────────────────────────
    cores = {
        "preto":          "preto",
        "preta":          "preto",
        "branco":         "branco",
        "branca":         "branco",
        "cinza mescla":   "cinza_mescla",
        "cinza chumbo":   "cinza_chumbo",
        "cinza":          "cinza_mescla",
        "marinho":        "marinho",
        "royal":          "royal",
        "vermelho":       "vermelho",
        "vermelha":       "vermelho",
        "vinho":          "vinho",
        "verde militar":  "verde_militar",
        "verde bandeira": "verde_bandeira",
        "amarelo":        "amarelo",
        "amarela":        "amarelo",
        "rosa":           "rosa",
        "azul":           "royal",
    }
    for chave, valor in cores.items():
        if normalizar(chave) in t:
            slots["cor"] = valor
            break

    # ── grade / tamanho ──────────────────────────────────────────
    if re.search(r'plus.?size|plus|g1|g2|g3|g4', t):
        slots["grade"] = "plus_size"
    elif re.search(r'infantil|crianca|kids', t):
        slots["grade"] = "infantil"
    elif re.search(r'\b(pp|p|m|g|gg|xgg)\b', t):
        slots["grade"] = "adulto"

    # ── uso / ocasião ────────────────────────────────────────────
    usos = {
        "verao":           "verao",
        "inverno intenso": "inverno_intenso",
        "inverno leve":    "inverno_leve",
        "inverno":         "inverno",
        "corporativo":     "corporativo",
        "esporte":         "esporte",
        "casual":          "casual",
        "dia a dia":       "dia_a_dia",
        "formal":          "formal",
        "meia estacao":    "meia_estacao",
    }
    for chave, valor in usos.items():
        if normalizar(chave) in t:
            slots["uso"] = valor
            break

    # ── urgência ─────────────────────────────────────────────────
    if re.search(r'urgente|pra ontem|com pressa|preciso rapido|prazo curto|adiantar', t):
        slots["urgente"] = True

    # ── número do pedido ─────────────────────────────────────────
    match_pedido = re.search(r'FF-\d{4}-\d{4}', mensagem, re.IGNORECASE)
    if match_pedido:
        slots["numero_pedido"] = match_pedido.group(0).upper()

    # ── metragem de tecido ───────────────────────────────────────
    match_metros = re.search(r'(\d+[\.,]?\d*)\s*(metros?|m\b)', t)
    if match_metros:
        slots["metragem"] = float(match_metros.group(1).replace(",", "."))

    # ── prazo desejado ───────────────────────────────────────────
    match_prazo = re.search(r'em\s*(\d+)\s*dias?|ate\s*(\d+)\s*dias?|prazo de\s*(\d+)', t)
    if match_prazo:
        valor = next(v for v in match_prazo.groups() if v is not None)
        slots["prazo_desejado"] = int(valor)

    return slots
