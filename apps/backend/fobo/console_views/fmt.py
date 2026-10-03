"""Display formatting, matching the console's own helpers exactly.

The console parses an adjustment's `amount` back into a number, so the
format here is a contract, not a style choice.
"""

from datetime import datetime

SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€"}


def money(value: float | None, ccy: str = "USD") -> str:
    """'USD 2,905.00', the console's money()."""
    if value is None:
        return "—"
    return f"{ccy} {value:,.2f}"


def money0(value: float, ccy: str = "USD") -> str:
    """'USD 15,965', the console's money0()."""
    return f"{ccy} {round(value):,}"


def amount(value: float, ccy: str = "USD") -> str:
    """An adjustment row's figure: '$2,340'."""
    return f"{SYMBOL.get(ccy, ccy + ' ')}{value:,.0f}"


def hhmm(value: datetime | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"
