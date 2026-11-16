"""Estimativa demonstrativa de entrega, sem cotação de transportadora."""
import re
from dataclasses import dataclass

FREE_SHIPPING_CENTS = 9900
SHIPPING_CENTS = 1290


@dataclass(frozen=True)
class ShippingEstimate:
    postal_code: str
    cost_cents: int
    minimum_days: int = 3
    maximum_days: int = 5


def estimate_shipping(postal_code, subtotal_cents):
    value = postal_code.strip()
    if not re.fullmatch(r'[0-9]{5}-?[0-9]{3}', value):
        raise ValueError('Informe um CEP com 8 números, como 01001-000.')
    digits = value.replace('-', '')
    if digits == '00000000':
        raise ValueError('Informe um CEP válido para simular a entrega.')
    if type(subtotal_cents) is not int or subtotal_cents < 0:
        raise ValueError('Subtotal inválido.')
    return ShippingEstimate(digits[:5]+'-'+digits[5:], 0 if subtotal_cents > FREE_SHIPPING_CENTS else SHIPPING_CENTS)
