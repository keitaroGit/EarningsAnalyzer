import os
import re
import json
import requests
import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY is not set in .env file")
print(f"API Key loaded: {api_key[:20]}...")

app = Flask(__name__)
client = Anthropic(api_key=api_key)
print("Anthropic client initialized successfully")

SEC_HEADERS = {"User-Agent": "EarningsAnalyzer keita@example.com"}


def get_cik_from_ticker(ticker):
    mapping_url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(mapping_url, headers=SEC_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            cik = str(entry["cik_str"]).zfill(10)
            return cik, entry.get("title", ticker_upper)
    raise Exception(f"ティッカー '{ticker}' が見つかりませんでした。")


def get_filing_text(cik, target_form):
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(submissions_url, headers=SEC_HEADERS, timeout=10)
    resp.raise_for_status()
    submissions = resp.json()
    filings = submissions.get("filings", {}).get("recent", {})
    forms             = filings.get("form", [])
    accession_numbers = filings.get("accessionNumber", [])
    dates             = filings.get("filingDate", [])
    primary_docs      = filings.get("primaryDocument", [])
    for i, form in enumerate(forms):
        if form == target_form:
            accession   = accession_numbers[i].replace("-", "")
            primary_doc = primary_docs[i]
            filing_date = dates[i]
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{primary_doc}"
            doc_resp = requests.get(doc_url, headers=SEC_HEADERS, timeout=15)
            doc_resp.raise_for_status()
            text = doc_resp.text
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:12000], filing_date
    raise Exception(f"{target_form} のフィリングが見つかりませんでした。")


def get_next_earnings_date(ticker):
    """次回決算発表日をAlpha Vantage / Nasdaq API経由で取得"""
    # 方法1: Nasdaq Earnings Calendar API
    try:
        url = f"https://api.nasdaq.com/api/calendar/earnings?date=2026-04-18"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
        }
        # 今後30日間を検索
        today = datetime.date.today()
        for days_ahead in range(0, 90, 7):
            check_date = today + datetime.timedelta(days=days_ahead)
            url = f"https://api.nasdaq.com/api/calendar/earnings?date={check_date.strftime('%Y-%m-%d')}"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("data", {}).get("rows", [])
                for row in rows:
                    if row.get("symbol", "").upper() == ticker.upper():
                        return check_date.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Nasdaq method failed: {e}")

    # 方法2: Yahoo Finance crumb方式
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        # まずcookieを取得
        session.get(f"https://finance.yahoo.com/quote/{ticker}", timeout=8)
        # crumbを取得
        crumb_resp = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=8)
        crumb = crumb_resp.text.strip()
        if crumb:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=calendarEvents&crumb={crumb}"
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("quoteSummary", {}).get("result", [])
                if result:
                    earnings = result[0].get("calendarEvents", {}).get("earnings", {})
                    dates = earnings.get("earningsDate", [])
                    if dates:
                        ts = dates[0].get("raw")
                        if ts:
                            dt = datetime.datetime.utcfromtimestamp(ts)
                            if dt.date() >= datetime.date.today():
                                return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Yahoo crumb method failed: {e}")

    return None


def analyze_with_claude(filing_text, ticker, form_type, filing_date, language):
    lang_label = "日本語" if language == "ja" else "English"
    form_descriptions = {
        "10-Q": "四半期報告書",
        "10-K": "年次報告書",
        "8-K":  "臨時報告書（重要事象）",
        "DEF 14A": "株主総会委任状説明書"
    }
    form_desc = form_descriptions.get(form_type, form_type)
    system_prompt = f"""あなたは決算報告書の専門アナリストです。
SEC EDGARから取得した{form_type}（{form_desc}）を分析して、以下の4項目を{lang_label}で詳しく説明してください。
【重要】この情報は「情報提供のみ」です。投資助言ではありません。
分析結果はJSONのみ返してください（説明文・コードブロック不要）:
{{
    "revenue_profit_summary": "売上・利益のサマリー（前年比を含む。8-Kの場合は主要開示内容、DEF 14Aの場合は議案・役員報酬の概要）",
    "analyst_comparison": "アナリスト予想との比較コメント（SEC書類に情報がない場合は「SEC書類には予想比較情報なし」と記載）",
    "management_topics": "経営陣の主要発言・トピック（箇条書き）",
    "investor_summary": "投資家向け一言まとめ（1-2文）",
    "disclaimer": "【情報提供のみ】本分析は情報提供目的であり、投資助言ではありません。投資判断は自己責任でお願いします。"
}}"""
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": f"ティッカー: {ticker}\n書類種別: {form_type}\n提出日: {filing_date}\n\n--- 書類テキスト ---\n{filing_text}"}]
    )
    response_text = message.content[0].text
    json_start = response_text.find('{')
    json_end   = response_text.rfind('}') + 1
    if json_start == -1:
        raise Exception("AIの応答からJSONを取得できませんでした")
    return json.loads(response_text[json_start:json_end])


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data        = request.get_json()
        ticker      = data.get('ticker', '').strip().upper()
        language    = data.get('language', 'ja')
        report_type = data.get('report_type', '10-Q')
        if not ticker:
            return jsonify({'error': 'ティッカーシンボルを入力してください'}), 400
        if report_type not in ('10-Q', '10-K', '8-K', 'DEF 14A'):
            return jsonify({'error': '無効な書類種別です'}), 400
        cik, company_name        = get_cik_from_ticker(ticker)
        filing_text, filing_date = get_filing_text(cik, report_type)
        result                   = analyze_with_claude(filing_text, ticker, report_type, filing_date, language)
        next_earnings            = get_next_earnings_date(ticker)
        print(f"Next earnings for {ticker}: {next_earnings}")
        return jsonify({
            'success':       True,
            'result':        result,
            'company_name':  company_name,
            'form_type':     report_type,
            'filing_date':   filing_date,
            'next_earnings': next_earnings
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)