"""Official human-only SMS Talent qualification rule."""

from decimal import Decimal, InvalidOperation


def qualify_talent(scores: list) -> str:
    """Three submitted human scores must each be strictly above 50."""
    if len(scores) != 3:
        raise ValueError("Exactly three human scores are required")

    normalized = []
    for score in scores:
        if score is None or isinstance(score, bool):
            raise ValueError("Invalid human score")
        try:
            value = Decimal(str(score))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Invalid human score") from None
        if not value.is_finite() or not Decimal("0") <= value <= Decimal("100"):
            raise ValueError("Human score must be between 0 and 100")
        normalized.append(value)

    if all(score > Decimal("50") for score in normalized):
        return "eligible_for_coaching"

    return "improvement_and_reevaluation"
