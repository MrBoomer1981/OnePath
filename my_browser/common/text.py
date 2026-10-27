"""Small text helpers used by both parts: money and Russian plurals."""


def rub_text(rub: float | None) -> str:
    """«0,87 ₽»: with a no-break space, so that «₽» never wraps to a line of its own on a narrow screen."""
    if rub is None:
        return "—"
    return f"{rub:.2f} ₽".replace(".", ",") if rub < 10 else f"{rub:.1f} ₽".replace(".", ",")


def plural(n: int, one: str, few: str, many: str) -> str:
    """The Russian word form for n: 1 день, 2 дня, 5 дней."""
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many
