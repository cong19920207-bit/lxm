"""Billing reconciliation uses frozen same-period/currency formula and no fake zero."""
from decimal import Decimal
import pytest


def test_billing_reconciliation_retains_formula_and_evidence():
    from backend.services.realtime_voice_billing_metric_service import reconcile_bill
    result=reconcile_bill(estimated_cost='12', billed_cost='10',
        estimate_period='2026-09', bill_period='2026-09',estimate_currency='CNY',bill_currency='CNY',
        evidence_locator='manual-bill-2026-09')
    assert result == {'period':'2026-09','currency':'CNY','estimated_cost':'12','provider_billed_cost':'10',
        'difference_amount':'2','difference_rate':'0.2','status':'measured','formula_version':'voice-bill-v1',
        'evidence_locator':'manual-bill-2026-09','estimate_label':'估算值'}


@pytest.mark.parametrize('estimate,bill,rate,status',[('0','0','0','measured'),('1','0',None,'not_measurable'),
    ('8','10','0.2','measured')])
def test_zero_denominator_and_absolute_rate(estimate,bill,rate,status):
    from backend.services.realtime_voice_billing_metric_service import reconcile_bill
    result=reconcile_bill(estimated_cost=estimate,billed_cost=bill,estimate_period='2026-09',bill_period='2026-09',
        estimate_currency='CNY',bill_currency='CNY',evidence_locator='manual-1')
    assert result['difference_rate']==rate and result['status']==status
    assert Decimal(result['difference_amount'])==Decimal(estimate)-Decimal(bill)


@pytest.mark.parametrize('field,value',[('bill_period','2026-08'),('bill_currency','USD'),
    ('estimated_cost','NaN'),('billed_cost','Infinity'),('estimated_cost','-1'),('evidence_locator','')])
def test_invalid_or_incomparable_input_is_rejected(field,value):
    from backend.services.realtime_voice_billing_metric_service import reconcile_bill
    args=dict(estimated_cost='12',billed_cost='10',estimate_period='2026-09',bill_period='2026-09',
        estimate_currency='CNY',bill_currency='CNY',evidence_locator='manual-1')
    args[field]=value
    with pytest.raises(ValueError):reconcile_bill(**args)
