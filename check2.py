import requests
headers = {'User-Agent': 'EarningsAnalyzer keita@example.com'}
url = 'https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json'
resp = requests.get(url, headers=headers)
facts = resp.json()
usgaap = facts['facts']['us-gaap']
items = usgaap.get('Revenues', {}).get('units', {}).get('USD', [])
quarterly = [i for i in items if i.get('form') in ('10-Q','10-K')]
quarterly.sort(key=lambda x: x['end'])
for i in quarterly[-10:]:
    print(i['end'], i['form'], round(i['val']/1e9, 2), 'B')