import requests
headers = {'User-Agent': 'EarningsAnalyzer keita@example.com'}
# CCLのCIKを取得
mapping = requests.get('https://www.sec.gov/files/company_tickers.json', headers=headers).json()
cik = None
for entry in mapping.values():
    if entry.get('ticker','').upper() == 'CCL':
        cik = str(entry['cik_str']).zfill(10)
        print(f"CIK: {cik}, Name: {entry['title']}")
        break

url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
resp = requests.get(url, headers=headers)
facts = resp.json()
usgaap = facts['facts']['us-gaap']
for key in ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'RevenueFromContractWithCustomerIncludingAssessedTax']:
    items = usgaap.get(key, {}).get('units', {}).get('USD', [])
    quarterly = [i for i in items if i.get('form') in ('10-Q','10-K')]
    if quarterly:
        quarterly.sort(key=lambda x: x['end'])
        latest = quarterly[-1]['end']
        print(f'{key}: {len(quarterly)} items, latest: {latest}, last value: {round(quarterly[-1]["val"]/1e9,2)}B')
    else:
        print(f'{key}: no data')