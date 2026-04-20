f = open('app.py', 'r', encoding='utf-8').read()
old = '            "RevenueFromContractWithCustomerExcludingAssessedTax",\n            "Revenues",'
new = '            "Revenues",\n            "RevenueFromContractWithCustomerExcludingAssessedTax",'
if old in f:
    f = f.replace(old, new)
    open('app.py', 'w', encoding='utf-8').write(f)
    print('done')
else:
    print('not found')