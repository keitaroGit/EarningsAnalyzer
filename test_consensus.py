import requests

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com",
})

# クッキー取得
r = session.get("https://finance.yahoo.com/quote/AAPL", timeout=8)
print(f"Cookie status: {r.status_code}")

# crumb取得
crumb_resp = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=8)
crumb = crumb_resp.text.strip()
print(f"Crumb: {crumb}")

if crumb:
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/AAPL?modules=earningsTrend&crumb={crumb}"
    resp = session.get(url, timeout=10)
    print(f"Status: {resp.status_code}")
    print(resp.text[:500])