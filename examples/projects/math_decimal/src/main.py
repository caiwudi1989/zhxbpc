from decimal import Decimal,ROUND_HALF_UP
amount=(Decimal("0.1")+Decimal("0.2")).quantize(Decimal("0.00"),rounding=ROUND_HALF_UP)
print(amount)
