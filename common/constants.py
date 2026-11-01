categories = ["Ação", "FII", "ETF", "Renda fixa", "Cripto", "Outro"]


allowed = {
    "APORTE": {"valor_liquido"},
    "RETIRADA": {"valor_liquido"},
    "TAXA": {"valor_liquido"},
    "COMPRA": {"quantidade", "preco", "taxas"},
    "VENDA": {"quantidade", "preco", "taxas"},
    "DIVIDENDO": {"valor_liquido"},
    "JCP": {"valor_bruto", "valor_liquido"},
    "BONIFICACAO": {"quantidade"},
    "DESDOBRAMENTO": {"fator"},
    "GRUPAMENTO": {"fator"},
    "AMORTIZACAO": {"valor_liquido"},
    "LIQUIDACAO": {"valor_liquido"},
}
