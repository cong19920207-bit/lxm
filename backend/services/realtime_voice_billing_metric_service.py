"""Pure manual-bill reconciliation. No provider calls or persistence.

Inputs must already refer to the same billing period and currency. This formula
is independently testable, but controlled fixtures do not verify a real bill.
"""
from decimal import Decimal, InvalidOperation, localcontext


def _amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('invalid_billing_amount')
    if len(str(value)) > 64:
        raise ValueError('invalid_billing_amount')
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError('invalid_billing_amount') from None
    if not amount.is_finite() or amount < 0 or amount > Decimal('1e18') or amount.as_tuple().exponent < -12:
        raise ValueError('invalid_billing_amount')
    return amount


def reconcile_bill(*, estimated_cost, billed_cost, estimate_period, bill_period,
                   estimate_currency, bill_currency, evidence_locator):
    """Return decimal strings; a nonzero estimate / zero bill has no rate."""
    if (not isinstance(estimate_period, str) or not estimate_period.strip() or
            len(estimate_period) > 64 or estimate_period != bill_period):
        raise ValueError('billing_period_mismatch')
    if (not isinstance(estimate_currency, str) or len(estimate_currency) != 3 or
            not estimate_currency.isascii() or not estimate_currency.isalpha() or
            estimate_currency != estimate_currency.upper() or estimate_currency != bill_currency):
        raise ValueError('billing_currency_mismatch')
    if not isinstance(evidence_locator, str) or not evidence_locator.strip() or len(evidence_locator) > 256:
        raise ValueError('billing_evidence_required')
    estimated, billed = _amount(estimated_cost), _amount(billed_cost)
    with localcontext() as context:
        context.prec = 40
        difference = estimated - billed
        rate = abs(difference) / billed if billed else Decimal(0) if not estimated else None
        return {'period': estimate_period, 'currency': estimate_currency,
                'estimated_cost': str(estimated), 'provider_billed_cost': str(billed),
                'difference_amount': str(difference),
                'difference_rate': str(rate) if rate is not None else None,
                'status': 'measured' if rate is not None else 'not_measurable',
                'formula_version': 'voice-bill-v1', 'evidence_locator': evidence_locator,
                'estimate_label': '估算值'}
