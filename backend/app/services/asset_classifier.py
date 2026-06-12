GOLD_ETF_SYMBOLS = {
    "GOLDBEES", "AXISGOLD", "HDFCGOLD", "SGOLD", "GOLDIETF",
    "NIPGOLD", "KOTAKGOLD", "GOLDSHARE", "BSLGOLDETF", "LICMFGOLD",
}

SILVER_ETF_SYMBOLS = {
    "SILVERBEES", "SILVRETF", "SILVERETF", "KOTAKSILV",
    "NIFTYSILV", "HDFCSILVER", "AXISSILVER",
}

LIQUID_ETF_SYMBOLS = {
    "LIQUIDBEES", "LIQUISETF", "KOTAKLIQUID", "AXISLIQUID",
}


def classify_holding(symbol: str, isin: str | None) -> str:
    """Returns one of: mutual_fund | gold_etf | silver_etf | liquid_etf | stock"""
    if isin and isin.startswith("INF"):
        return "mutual_fund"

    # Groww MF names contain "Fund" / "Scheme"; no stock ticker looks like this
    symbol_upper = symbol.upper()
    if " FUND" in symbol_upper or " SCHEME" in symbol_upper:
        return "mutual_fund"

    upper = symbol_upper.replace("-", "").replace(" ", "")
    if upper in GOLD_ETF_SYMBOLS:
        return "gold_etf"
    if upper in SILVER_ETF_SYMBOLS:
        return "silver_etf"
    if upper in LIQUID_ETF_SYMBOLS:
        return "liquid_etf"

    return "stock"
