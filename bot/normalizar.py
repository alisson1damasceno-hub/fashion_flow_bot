"""
normalizar.py — Função ÚNICA de normalização de texto.

Usada por vários módulos (classifier, extractor, contexto, responder, seguranca).
Deixa o texto "comparável": tudo em minúsculo e SEM acento, pra que "Olá" e
"ola" sejam tratados como iguais na hora de procurar palavras-chave.

Antes essa mesma função estava copiada em 5 arquivos; agora mora só aqui.
"""
import unicodedata


def normalizar(texto):
    """
    Passa o texto pra minúsculo e remove os acentos. Ex: "Coração" -> "coracao".
    """
    texto = texto.lower()
    # NFD separa a letra do acento (ex: 'á' vira 'a' + '´'); aí descartamos os
    # acentos (categoria 'Mn' = "mark, nonspacing", ou seja, sinal sobre a letra).
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")
