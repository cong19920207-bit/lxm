"""Explicit simulated pricing for development; never a default business price."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from backend.services.realtime_voice_billing_metric_service import _amount


def estimate_amount(seconds, unit_price, unit):
    if type(seconds) is not int or seconds < 0 or unit not in ('minute', 'second'):
        raise ValueError('invalid_pricing_input')
    price = _amount(unit_price)
    with localcontext() as context:
        context.prec = 48
        value = (Decimal(seconds) * price / (60 if unit == 'minute' else 1)).quantize(
            Decimal('0.000001'), rounding=ROUND_HALF_UP)
    return _amount(value)


@dataclass(frozen=True)
class SimulatedPricing:
    unit_price: str
    unit: str = 'minute'
    currency: str = 'CNY'

    def __post_init__(self):
        price = _amount(self.unit_price)
        if self.unit not in ('minute', 'second') or not (isinstance(self.currency, str) and
                len(self.currency) == 3 and self.currency.isascii() and
                self.currency.isalpha() and self.currency.isupper()):
            raise ValueError('invalid_pricing_input')
        # Decimal.normalize() rounds under the ambient context (usually 28 digits),
        # which can collapse distinct legal prices into the same dimension hash.
        canonical = format(price, 'f') if price else '0'
        if '.' in canonical:
            canonical = canonical.rstrip('0').rstrip('.')
        object.__setattr__(self, 'unit_price', canonical)

    def dimensions(self):
        return dict(data_source='simulated', unit_price=self.unit_price, unit=self.unit,
                    currency=self.currency, rounding='half_up_6_decimal_places')

    def estimate(self, seconds):
        return estimate_amount(seconds, self.unit_price, self.unit)


SIMULATED_PRICING = SimulatedPricing('0.06')
