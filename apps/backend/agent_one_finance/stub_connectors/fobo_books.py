"""The FOBO groups' master books in APAC, EMEA and the Americas, for the stand-in
CATS and MOTIF (finance.py): Rates (FOBO group 500081, about 700 books) and FI Credit
(500082, about 1,200), each book holding one product.

FOBO's feed sends one event per group, region and COB ("FOBO CSV loaded" for Rates
EMEA on 2026-10-08), and a task reconciles every book of that group in that region
at once (the regional tools in finance.py: cats.group_positions, ...).

The same books are reference data (config/agent-one-finance/knowledge/fobo-books-*.yaml,
written from this module by scripts/write_fobo_books.py; a test keeps them the same),
which gives every book its business, region, desk, product and label, and every
group its name.

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
from dataclasses import dataclass, field

TENORS = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"]
# Region code (in book ids and FOBO's events) -> region name in the reference data.
REGION_NAMES = {"APAC": "APAC", "EMEA": "EMEA", "AMER": "Americas"}


@dataclass(frozen=True)
class Business:
    group: str                 # FOBO group id, as FOBO's events name it
    name: str
    prefix: str                # book ids: <prefix>-<region code>-0001
    seed: str                  # stand-in data seed, per business
    # Region code -> legal entity, books, desks and their products (with their weight in the region's books).
    regions: dict
    products: dict[str, list[str]]
    new_issues: dict[str, str] = field(default_factory=dict)   # product -> an instrument MOTIF may not have yet
    clean_share: float = 0.86                                  # books with no break of their own on a COB


def _new_issue(first: str) -> str:
    head, last = first.rsplit(" ", 1)
    return f"{head} {int(last) + 5}" if last.isdigit() else f"{first} S46"


FI_CREDIT_PRODUCTS = {
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

FI_CREDIT = Business(
    group="500082", name="FI Credit", prefix="FIC", seed="fic",
    regions={
        "APAC": {"legal_entity": "LE-APAC-01", "books": 320, "desks": {
            "FIC-APAC-IG": {"Asia IG bonds": 4, "Japan corporates": 2, "Australia corporates": 2},
            "FIC-APAC-HY": {"Asia HY bonds": 2},
            "FIC-APAC-CDS": {"iTraxx Asia": 2},
        }},
        "EMEA": {"legal_entity": "LE-UK-01", "books": 480, "desks": {
            "FIC-EMEA-IG": {"EUR IG corporates": 4, "GBP corporates": 2},
            "FIC-EMEA-HY": {"EUR HY bonds": 2},
            "FIC-EMEA-FIN": {"Sub financials": 1},
            "FIC-EMEA-CDS": {"iTraxx Europe": 2},
        }},
        "AMER": {"legal_entity": "LE-US-01", "books": 440, "desks": {
            "FIC-AMER-IG": {"USD IG corporates": 4},
            "FIC-AMER-HY": {"USD HY bonds": 2},
            "FIC-AMER-EM": {"LatAm corporates": 1},
            "FIC-AMER-CDS": {"CDX": 2},
            "FIC-AMER-CONV": {"Convertibles": 1},
        }},
    },
    products=FI_CREDIT_PRODUCTS,
    new_issues={product: _new_issue(instruments[0]) for product, instruments in FI_CREDIT_PRODUCTS.items()},
)

RATES = Business(
    group="500081", name="Rates", prefix="RATES", seed="rates", clean_share=0.82,
    regions={
        "EMEA": {"legal_entity": "LE-UK-01", "books": 300, "desks": {
            "RATES-EMEA-EUR": {"EUR swaps": 4, "EUR govt bonds": 2},
            "RATES-EMEA-GBP": {"GBP swaps": 3, "Gilts": 1},
            "RATES-EMEA-INFL": {"Inflation swaps": 1},
            "RATES-EMEA-STIR": {"STIR futures": 2},
        }},
        "APAC": {"legal_entity": "LE-APAC-01", "books": 160, "desks": {
            "RATES-APAC-JPY": {"JPY swaps": 3, "JGBs": 2},
            "RATES-APAC-AUD": {"AUD swaps": 2},
            "RATES-APAC-XCCY": {"Asia cross-currency swaps": 1},
        }},
        "AMER": {"legal_entity": "LE-US-01", "books": 260, "desks": {
            "RATES-AMER-USD": {"USD swaps": 4, "US Treasuries": 3},
            "RATES-AMER-OPT": {"USD swaptions": 1},
            "RATES-AMER-STIR": {"SOFR futures": 2},
        }},
    },
    products={
        "EUR swaps": [*(f"IRS {t} EUR" for t in TENORS), "ESTR OIS 1Y", "ESTR OIS 3Y"],
        "EUR govt bonds": ["BUND 2Y", "BUND 5Y", "BUND 10Y", "BUND 30Y", "BOBL 5Y", "OAT 5Y", "OAT 10Y", "OAT 30Y"],
        "GBP swaps": [*(f"IRS {t} GBP" for t in TENORS), "SONIA OIS 1Y", "SONIA OIS 3Y"],
        "Gilts": ["GILT 2Y", "GILT 5Y", "GILT 10Y", "GILT 15Y", "GILT 30Y", "UKTB 3M"],
        "Inflation swaps": ["UKRPI ZC 5Y", "UKRPI ZC 10Y", "UKRPI ZC 20Y", "UKRPI ZC 30Y",
                            "EUHICP ZC 5Y", "EUHICP ZC 10Y", "EUHICP ZC 20Y"],
        "STIR futures": ["EURIBOR FUT Z6", "EURIBOR FUT H7", "EURIBOR FUT M7", "SONIA FUT Z6", "SONIA FUT H7",
                         "BUND FUT", "BOBL FUT", "GILT FUT"],
        "JPY swaps": [*(f"IRS {t} JPY" for t in TENORS), "TONA OIS 1Y", "TONA OIS 3Y"],
        "JGBs": ["JGB 2Y", "JGB 5Y", "JGB 10Y", "JGB 20Y", "JGB 30Y", "JGB 40Y"],
        "AUD swaps": [*(f"IRS {t} AUD" for t in TENORS), "ACGB 3Y", "ACGB 10Y"],
        "Asia cross-currency swaps": ["XCCY USDJPY 2Y", "XCCY USDJPY 5Y", "XCCY USDJPY 10Y",
                                      "XCCY AUDUSD 2Y", "XCCY AUDUSD 5Y", "XCCY AUDUSD 10Y"],
        "USD swaps": [*(f"IRS {t} USD" for t in TENORS), "SOFR OIS 1Y", "SOFR OIS 3Y", "BASIS SOFR-FF 5Y"],
        "US Treasuries": ["UST 1Y", "UST 2Y", "UST 3Y", "UST 5Y", "UST 7Y", "UST 10Y", "UST 20Y", "UST 30Y",
                          "TIPS 5Y", "TIPS 10Y"],
        "USD swaptions": ["SWPTN 3M10Y USD", "SWPTN 6M5Y USD", "SWPTN 1Y5Y USD", "SWPTN 1Y10Y USD",
                          "SWPTN 2Y10Y USD", "SWPTN 5Y5Y USD", "SWPTN 5Y10Y USD", "SWPTN 10Y10Y USD"],
        "SOFR futures": ["SOFR FUT Z6", "SOFR FUT H7", "SOFR FUT M7", "SOFR FUT U7",
                         "UST 2Y FUT", "UST 5Y FUT", "UST 10Y FUT"],
    },
    # A new tenor, line or contract per product.
    new_issues={"EUR swaps": "IRS 12Y EUR", "EUR govt bonds": "BUND 15Y", "GBP swaps": "IRS 12Y GBP",
                "Gilts": "GILT 40Y", "Inflation swaps": "UKRPI ZC 15Y", "STIR futures": "EURIBOR FUT U7",
                "JPY swaps": "IRS 12Y JPY", "JGBs": "JGB 15Y", "AUD swaps": "IRS 12Y AUD",
                "Asia cross-currency swaps": "XCCY USDKRW 5Y", "USD swaps": "IRS 12Y USD", "US Treasuries": "UST 25Y",
                "USD swaptions": "SWPTN 2Y5Y USD", "SOFR futures": "SOFR FUT Z7"},
)

BUSINESSES = {b.group: b for b in (RATES, FI_CREDIT)}
INSTRUMENTS = sorted({i for b in BUSINESSES.values() for p in b.products.values() for i in p}
                     | {i for b in BUSINESSES.values() for i in b.new_issues.values()})


def _rng(*parts: str) -> random.Random:
    return random.Random("|".join(parts))


def _books() -> dict[str, dict]:
    out = {}
    for biz in BUSINESSES.values():
        for code, region in biz.regions.items():
            weighted = [(desk, product) for desk, products in region["desks"].items()
                        for product, weight in products.items() for _ in range(weight)]
            name = REGION_NAMES[code]
            for n in range(1, region["books"] + 1):
                book = f"{biz.prefix}-{code}-{n:04d}"
                desk, product = _rng(f"{biz.seed}-product", book).choice(weighted)
                out[book] = {"book": book, "group": biz.group, "business": biz.name, "region": name,
                             "region_code": code, "desk": desk, "product": product,
                             "legal_entity": region["legal_entity"],
                             "label": f"{biz.name} {name} · {product} ({book})"}
    return out


BOOKS = _books()


def is_book(book: str) -> bool:
    return book in BOOKS


def business(book: str) -> Business:
    return BUSINESSES[BOOKS[book]["group"]]


def books_in(group: str | int, region: str) -> list[str]:
    """Every master book of a FOBO group in a region (code: EMEA, APAC, AMER)."""
    group, region = str(group), str(region).upper()
    return [b for b, info in BOOKS.items() if info["group"] == group and info["region_code"] == region]


def instruments(book: str, cob: str) -> list[str]:
    biz, info = business(book), BOOKS[book]
    held = biz.products[info["product"]]
    issue = region_issue(biz, info["region_code"], cob)
    if issue and issue["kind"] == "static" and issue["product"] == info["product"]:
        return [*held, biz.new_issues[issue["product"]]]
    return held


def region_issue(biz: Business, region: str, cob: str) -> dict | None:
    """The one problem a group's region has across many books on a COB, if any."""
    r = _rng(f"{biz.seed}-region-issue", REGION_NAMES[region], cob)
    roll = r.random()
    products = [p for desk in biz.regions[region]["desks"].values() for p in desk]
    if roll < 0.3:
        return {"kind": "static", "product": r.choice(products)}
    if roll < 0.6:
        return {"kind": "settle"}
    return None


def clean(book: str, cob: str) -> bool:
    biz = business(book)
    return _rng(f"{biz.seed}-clean", book, cob).random() < biz.clean_share


def issue_instrument(book: str, cob: str) -> tuple[str, str] | None:
    """(instrument, kind) of the region's problem in this book on this COB."""
    biz, info = business(book), BOOKS[book]
    issue = region_issue(biz, info["region_code"], cob)
    if issue is None:
        return None
    if issue["kind"] == "static":
        return (biz.new_issues[issue["product"]], "static") if issue["product"] == info["product"] else None
    if _rng(f"{biz.seed}-settle-book", book, cob).random() < 0.35:
        return _rng(f"{biz.seed}-settle-ins", book, cob).choice(biz.products[info["product"]]), "settle"
    return None


def settle_amount(book: str, cob: str) -> float:
    """What the settlement batch loaded twice adds to the instrument in MOTIF."""
    return _rng(f"{business(book).seed}-settle-amt", book, cob).uniform(2_000, 40_000)
