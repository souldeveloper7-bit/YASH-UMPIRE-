from decimal import Decimal, ROUND_HALF_UP
_CENT=Decimal('0.01')
def money(value):
    return Decimal(str(value)).quantize(_CENT,rounding=ROUND_HALF_UP)
def fee_split(amount):
    gross=money(amount)
    platform=money(gross*Decimal('0.01'))
    maintenance=money(gross*Decimal('0.01'))
    owner=money(gross*Decimal('0.03'))
    total_fee=money(platform+maintenance+owner)
    net=money(gross-total_fee)
    return {'gross':float(gross),'platform_fee':float(platform),'maintenance_fee':float(maintenance),'owner_fee':float(owner),'total_fee':float(total_fee),'seller_net':float(net)}
