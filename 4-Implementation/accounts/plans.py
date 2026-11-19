"""The plans shown on the pricing page. Change prices and sizes here, nothing else needs editing."""
from dataclasses import dataclass
from decimal import Decimal

UNLIMITED_DAYS = 30


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    searches: int | None          # None means unlimited
    price: Decimal
    tagline: str
    popular: bool = False

    @property
    def is_unlimited(self):
        return self.searches is None

    @property
    def per_search(self):
        """Price of one analysis, or None for the unlimited plan."""
        if self.searches is None:
            return None
        return (self.price / self.searches).quantize(Decimal("0.01"))


PLANS = (
    Plan("starter", "Starter", 20, Decimal("4.99"), "Try TerraRisk on a few fields or properties."),
    Plan("plus", "Plus", 30, Decimal("6.99"), "For small farms and house hunting."),
    Plan("pro", "Pro", 50, Decimal("9.99"), "The best balance for most people.", popular=True),
    Plan("business", "Business", 100, Decimal("17.99"), "For agencies, analysts and investors."),
    Plan("unlimited", "Unlimited", None, Decimal("29.00"), f"Run as many analyses as you need for {UNLIMITED_DAYS} days."),
)


def get_plan(key):
    return next((p for p in PLANS if p.key == key), None)
