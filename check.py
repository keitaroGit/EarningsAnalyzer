import requests
headers = {'User-Agent': 'EarningsAnalyzer keita@example.com'}
url = 'https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json'
resp = requests.get(url, headers=headers)
facts = resp.json()
usgaap = facts['facts']['us-gaap']
for key in ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet']:
    items = usgaap.get(key, {}).get('units', {}).get('USD', [])
    quarterly = [i for i in items if i.get('form') in ('10-Q','10-K')]
    if quarterly:
        quarterly.sort(key=lambda x: x['end'])
        latest = quarterly[-1]['end']
        print(f'{key}: {len(quarterly)} items, latest: {latest}')
    else:
        print(f'{key}: no data')