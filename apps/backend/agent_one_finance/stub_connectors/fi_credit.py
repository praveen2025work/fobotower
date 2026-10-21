"""The FI Credit master books in APAC, EMEA and the Americas, for the stand-in
CATS and MOTIF (finance.py): about 1,200 books, each holding one product.

The same books are reference data (config/agent-one-finance/knowledge/fobo-books-fi-credit.yaml,
written from this module by scripts/write_fi_credit_books.py; a test keeps the two
the same), which gives every book its business, region, desk, product and label.

What the books look like on a COB, deterministically:
  - most reconcile clean: CATS and MOTIF agree on every position;
  - some have breaks of their own, with the causes FOBO's checks find (finance.py);
  - a region can have one problem across many books on a COB (`region_issue`):
      static   a new issue not yet set up in MOTIF static data, in every book
               of one product (FOBO check C2: a data quality break, DO NOT POST)
      settle   a MOTIF settlement batch loaded twice, one instrument in about a
               third of the region's books (check C6: a settlement break, POST)
"""

import random

BUSINESS = "FI Credit"

# Region code in the book id -> region name, legal entity, books, desks and their products.
# Products are listed with their weight in the region's books.
REGIONS = {
    "APAC": {"name": "APAC", "legal_entity": "LE-APAC-01", "books": 320, "desks": {
        "FIC-APAC-IG": {"Asia IG bonds": 4, "Japan corporates": 2, "Australia corporates": 2},
        "FIC-APAC-HY": {"Asia HY bonds": 2},
        "FIC-APAC-CDS": {"iTraxx Asia": 2},
    }},
    "EMEA": {"name": "EMEA", "legal_entity": "LE-UK-01", "books": 480, "desks": {
        "FIC-EMEA-IG": {"EUR IG corporates": 4, "GBP corporates": 2},
        "FIC-EMEA-HY": {"EUR HY bonds": 2},
        "FIC-EMEA-FIN": {"Sub financials": 1},
        "FIC-EMEA-CDS": {"iTraxx Europe": 2},
    }},
    "AMER": {"name": "Americas", "legal_entity": "LE-US-01", "books": 440, "desks": {
        "FIC-AMER-IG": {"USD IG corporates": 4},
        "FIC-AMER-HY": {"USD HY bonds": 2},
        "FIC-AMER-EM": {"LatAm corporates": 1},
        "FIC-AMER-CDS": {"CDX": 2},
        "FIC-AMER-CONV": {"Convertibles": 1},
    }},
}

PRODUCTS = {
    "Asia IG bonds": ["BOND HKLAND 2030", "BOND CKHH 2031", "BOND TENCENT 2030", "BOND ALIBABA 2031", "BOND DBS 2029",
                      "BOND SINGTEL 2032", "BOND PTT 2030", "BOND RELIANCE 2033", "BOND KEPCO 2029", "BOND SPGRID 2031"],
    "Japan corporates": ["BOND TOYOTA 2030", "BOND NTT 2031", "BOND MUFG 2029", "BOND SONY 2032", "BOND HITACHI 2030",
                         "BOND SOFTBANK 2028", "BOND NOMURA 2031", "BOND MIZUHO 2030"],
    "Australia corporates": ["BOND BHP 2031", "BOND TELSTRA 2030", "BOND WESFARMERS 2029", "BOND ANZ 2032",
                             "BOND NAB 2030", "BOND WOOLWORTHS 2031", "BOND QANTAS 2029", "BOND SANTOS 2030"],
    "Asia HY bonds": ["BOND VEDANTA 2028", "BOND MEDCO 2029", "BOND GREENKO 2027", "BOND ADANIGR 2030",
                      "BOND LONGFOR 2028", "BOND MGMCHINA 2029", "BOND STUDIOCITY 2028", "BOND JSWSTEEL 2030"],
    "iTraxx Asia": ["ITRAXX ASIA IG 5Y", "ITRAXX ASIA IG 10Y", "ITRAXX AUS 5Y", "ITRAXX JAPAN 5Y", "CDS TOYOTA 5Y",
                    "CDS SONY 5Y", "CDS SOFTBANK 5Y", "CDS BHP 5Y", "CDS TELSTRA 5Y", "CDS KOREA 5Y"],
    "EUR IG corporates": ["BOND SIEMENS 2031", "BOND TOTAL 2030", "BOND VW 2029", "BOND BMW 2032", "BOND SANOFI 2030",
                          "BOND ENEL 2031", "BOND IBERDROLA 2033", "BOND ORANGE 2029", "BOND AIRBUS 2030", "BOND NESTLE 2031"],
    "GBP corporates": ["BOND VODAFONE 2034", "BOND TESCO 2030", "BOND BAT 2031", "BOND NGRID 2035", "BOND BP 2032",
                       "BOND GSK 2033", "BOND HSBC 2030", "BOND LLOYDS 2031"],
    "EUR HY bonds": ["BOND TELEFONICA 2029", "BOND RENAULT 2028", "BOND SCHAEFFLER 2029", "BOND ZF 2030",
                     "BOND ALTICE 2027", "BOND TKA 2028", "BOND INEOS 2029", "BOND CIRSA 2028"],
    "Sub financials": ["BOND DB AT1 2030", "BOND UBS AT1 2031", "BOND BNP T2 2033", "BOND SAN AT1 2029",
                       "BOND ISP T2 2032", "BOND ING T2 2031", "BOND HSBC AT1 2030", "BOND AXA T2 2032"],
    "iTraxx Europe": ["ITRAXX MAIN 5Y", "ITRAXX MAIN 10Y", "ITRAXX XOVER 5Y", "ITRAXX SNRFIN 5Y", "ITRAXX SUBFIN 5Y",
                      "CDS VW 5Y", "CDS DB 5Y", "CDS RENAULT 5Y", "CDS TOTAL 5Y", "CDS SIEMENS 5Y"],
    "USD IG corporates": ["BOND APPLE 2031", "BOND MSFT 2032", "BOND JPM 2030", "BOND VERIZON 2033", "BOND ATT 2031",
                          "BOND COMCAST 2030", "BOND PFIZER 2032", "BOND BOEING 2029", "BOND ORACLE 2031", "BOND AMZN 2033"],
    "USD HY bonds": ["BOND FORD 2029", "BOND CARNIVAL 2028", "BOND CHARTER 2030", "BOND TENET 2029", "BOND UAL 2028",
                     "BOND DISH 2027", "BOND OXY 2030", "BOND HCA 2031"],
    "LatAm corporates": ["BOND PEMEX 2030", "BOND PETROBRAS 2031", "BOND VALE 2032", "BOND CEMEX 2029", "BOND AMX 2030",
                         "BOND ECOPETROL 2031", "BOND FALABELLA 2029", "BOND CODELCO 2033"],
    "CDX": ["CDX IG 5Y", "CDX IG 10Y", "CDX HY 5Y", "CDX EM 5Y", "CDS FORD 5Y", "CDS GM 5Y", "CDS BOEING 5Y",
            "CDS ATT 5Y", "CDS MEXICO 5Y", "CDS BRAZIL 5Y"],
    "Convertibles": ["CONV TESLA 2028", "CONV COIN 2029", "CONV DKNG 2030", "CONV RIVN 2029", "CONV SPOT 2030",
                     "CONV SNAP 2028", "CONV UBER 2029", "CONV AFRM 2027"],
}


def _new_issue(first: str) -> str:
    head, last = first.rsplit(" ", 1)
    return f"{head} {int(last) + 5}" if last.isdigit() else f"{first} S46"


# A new issue (or index series) per product, which MOTIF static data may not have yet.
NEW_ISSUES = {product: _new_issue(instruments[0]) for product, instruments in PRODUCTS.items()}
INSTRUMENTS = sorted({i for p in PRODUCTS.values() for i in p} | set(NEW_ISSUES.values()))

CLEAN_SHARE = 0.86          # books with no break of their own on a COB


def _rng(*parts: str) -> random.Random:
    return random.Random("|".join(parts))


def _books() -> dict[str, dict]:
    out = {}
    for code, region in REGIONS.items():
        weighted = [(desk, product) for desk, products in region["desks"].items()
                    for product, weight in products.items() for _ in range(weight)]
        for n in range(1, region["books"] + 1):
            book = f"FIC-{code}-{n:04d}"
            desk, product = _rng("fic-product", book).choice(weighted)
            out[book] = {"book": book, "business": BUSINESS, "region": region["name"], "desk": desk,
                         "product": product, "legal_entity": region["legal_entity"],
                         "label": f"{BUSINESS} {region['name']} · {product} ({book})"}
    return out


BOOKS = _books()


def is_book(book: str) -> bool:
    return book in BOOKS


def instruments(book: str, cob: str) -> list[str]:
    held = PRODUCTS[BOOKS[book]["product"]]
    issue = region_issue(BOOKS[book]["region"], cob)
    if issue and issue["kind"] == "static" and issue["product"] == BOOKS[book]["product"]:
        return [*held, NEW_ISSUES[issue["product"]]]
    return held


def region_issue(region: str, cob: str) -> dict | None:
    """The one problem a region has across many books on a COB, if any."""
    r = _rng("fic-region-issue", region, cob)
    roll = r.random()
    products = [p for desk in next(x for x in REGIONS.values() if x["name"] == region)["desks"].values() for p in desk]
    if roll < 0.3:
        return {"kind": "static", "product": r.choice(products)}
    if roll < 0.6:
        return {"kind": "settle"}
    return None


def clean(book: str, cob: str) -> bool:
    return _rng("fic-clean", book, cob).random() < CLEAN_SHARE


def issue_instrument(book: str, cob: str) -> tuple[str, str] | None:
    """(instrument, kind) of the region's problem in this book on this COB."""
    info = BOOKS[book]
    issue = region_issue(info["region"], cob)
    if issue is None:
        return None
    if issue["kind"] == "static":
        return (NEW_ISSUES[issue["product"]], "static") if issue["product"] == info["product"] else None
    if _rng("fic-settle-book", book, cob).random() < 0.35:
        return _rng("fic-settle-ins", book, cob).choice(PRODUCTS[info["product"]]), "settle"
    return None
