def innings_to_outs(value: str | int | float | None) -> int:
    if value in (None, ""):
        return 0
    text = str(value)
    whole, dot, fraction = text.partition(".")
    fraction = fraction or "0"
    if not whole.lstrip("-").isdigit() or fraction not in {"0", "1", "2"}:
        raise ValueError(f"Invalid baseball innings value: {value}")
    return int(whole) * 3 + int(fraction)


def outs_to_innings(outs: int) -> str:
    if outs < 0:
        raise ValueError("Outs cannot be negative")
    return f"{outs // 3}.{outs % 3}"

