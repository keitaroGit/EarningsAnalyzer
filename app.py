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
    raise Exception(f"Ticker '{ticker}' not found.")


def extract_relevant_text(raw_text, form_type):
    """書類種別ごとに重要セクションを狙い撃ちして抽出"""
    MAX_CHARS = 50000

    # 書類種別ごとのキーワード優先順位
    keywords_map = {
        "10-Q": [
            "CONSOLIDATED STATEMENTS OF OPERATIONS",
            "CONSOLIDATED STATEMENTS OF INCOME",
            "STATEMENTS OF OPERATIONS",
            "STATEMENTS OF INCOME",
            "RESULTS OF OPERATIONS",
            "Financial Statements",
        ],
        "10-K": [
            "CONSOLIDATED STATEMENTS OF OPERATIONS",
            "CONSOLIDATED STATEMENTS OF INCOME",
            "STATEMENTS OF OPERATIONS",
            "STATEMENTS OF INCOME",
            "RESULTS OF OPERATIONS",
            "Financial Statements",
        ],
        "8-K": [
            "Item 2.02",
            "Results of Operations and Financial Condition",
            "Item 2.01",
            "Item 1.01",
            "RESULTS OF OPERATIONS",
        ],
        "DEF 14A": [
            "EXECUTIVE COMPENSATION",
            "Executive Compensation",
            "COMPENSATION DISCUSSION",
            "Compensation Discussion",
            "SUMMARY COMPENSATION TABLE",
            "Summary Compensation Table",
        ],
    }

    keywords = keywords_map.get(form_type, [])

    # キーワードを探して該当箇所から抽出
    text_upper = raw_text.upper()
    for keyword in keywords:
        idx = text_upper.find(keyword.upper())
        if idx != -1:
            # キーワードの少し前から取得（前後の文脈も含める）
            start = max(0, idx - 500)
            end = min(len(raw_text), idx + MAX_CHARS)
            extracted = raw_text[start:end]
            print(f"Found keyword '{keyword}' at index {idx}, extracting {len(extracted)} chars")
            return extracted

    # キーワードが見つからない場合は先頭から50,000文字
    print(f"No keyword found for {form_type}, using first {MAX_CHARS} chars")
    return raw_text[:MAX_CHARS]


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
            # HTMLタグ除去
            text = doc_resp.text
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            # 書類種別に応じた重要セクション抽出
            extracted = extract_relevant_text(text, target_form)
            return extracted, filing_date
    raise Exception(f"{target_form} filing not found.")


def get_financial_history(cik, ticker):
    """SEC EDGAR XBRLから過去8期分の財務データを取得"""
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        facts = resp.json()
        us_gaap = facts.get("facts", {}).get("us-gaap", {})

        revenue_keys = [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueGoodsNet",
        ]
        income_keys = [
            "NetIncomeLoss",
            "ProfitLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ]

        def extract_quarterly(key):
            data = us_gaap.get(key, {})
            units = data.get("units", {})
            usd = units.get("USD", [])
            quarterly = []
            seen = set()
            for item in usd:
                form = item.get("form", "")
                if form in ("10-Q", "10-K"):
                    end = item.get("end", "")
                    val = item.get("val", 0)
                    accn = item.get("accn", "")
                    if end and accn not in seen:
                        seen.add(accn)
                        quarterly.append({"period": end, "value": val, "form": form})
            quarterly.sort(key=lambda x: x["period"])
            return quarterly[-8:] if len(quarterly) >= 2 else []

        revenue_data = []
        for key in revenue_keys:
            revenue_data = extract_quarterly(key)
            if revenue_data:
                break

        income_data = []
        for key in income_keys:
            income_data = extract_quarterly(key)
            if income_data:
                break

        def to_billions(items):
            return [
                {
                    "period": item["period"],
                    "value": round(item["value"] / 1_000_000_000, 2),
                    "form": item["form"]
                }
                for item in items
            ]

        return {
            "revenue": to_billions(revenue_data),
            "net_income": to_billions(income_data),
            "currency": "USD Billions"
        }

    except Exception as e:
        print(f"Financial history error: {e}")
        return {"revenue": [], "net_income": [], "currency": "USD Billions"}


def get_next_earnings_date(ticker, cik):
    try:
        today = datetime.date.today()
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = requests.get(submissions_url, headers=SEC_HEADERS, timeout=10)
        resp.raise_for_status()
        submissions = resp.json()
        filings = submissions.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        quarterly_dates = []
        for i, form in enumerate(forms):
            if form in ("10-Q", "10-K"):
                try:
                    d = datetime.date.fromisoformat(dates[i])
                    quarterly_dates.append((d, form))
                except Exception:
                    pass
        if len(quarterly_dates) >= 2:
            quarterly_dates.sort(reverse=True)
            latest = quarterly_dates[0][0]
            second = quarterly_dates[1][0]
            delta = latest - second
            next_date = latest + delta
            if next_date > today:
                return next_date.strftime("%Y-%m-%d") + " (est.)"
            next_date2 = next_date + delta
            if next_date2 > today:
                return next_date2.strftime("%Y-%m-%d") + " (est.)"
    except Exception as e:
        print(f"Next earnings error: {e}")
    return None


def analyze_with_claude(filing_text, ticker, form_type, filing_date, language):
    lang_label = "Japanese" if language == "ja" else "English"
    form_descriptions = {
        "10-Q": "Quarterly Report",
        "10-K": "Annual Report",
        "8-K":  "Current Report (Material Events)",
        "DEF 14A": "Proxy Statement"
    }
    form_desc = form_descriptions.get(form_type, form_type)

    system_prompt = f"""You are an expert financial analyst specializing in SEC filings.
Analyze the provided {form_type} ({form_desc}) and respond in {lang_label}.
Focus on extracting specific numbers, percentages, and figures from the text.
Return ONLY a JSON object with no additional text or code blocks:
{{
    "revenue_profit_summary": "Detailed revenue and profit summary with specific numbers and YoY comparison. For 8-K: key disclosure content. For DEF 14A: executive compensation and proposals summary.",
    "management_topics": "Key management statements and topics (bullet points with specific details)",
    "investor_summary": "One or two sentence summary for investors highlighting the most important points",
    "disclaimer": "This analysis is for informational purposes only and does not constitute investment advice. Please make investment decisions at your own risk."
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Ticker: {ticker}\nForm: {form_type}\nFiling Date: {filing_date}\n\n--- Filing Text ---\n{filing_text}"}]
    )
    response_text = message.content[0].text
    json_start = response_text.find('{')
    json_end   = response_text.rfind('}') + 1
    if json_start == -1:
        raise Exception("Could not parse JSON from AI response")
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
            return jsonify({'error': 'Please enter a ticker symbol'}), 400
        if report_type not in ('10-Q', '10-K', '8-K', 'DEF 14A'):
            return jsonify({'error': 'Invalid report type'}), 400
        cik, company_name        = get_cik_from_ticker(ticker)
        filing_text, filing_date = get_filing_text(cik, report_type)
        result                   = analyze_with_claude(filing_text, ticker, report_type, filing_date, language)
        next_earnings            = get_next_earnings_date(ticker, cik)
        financial_history        = get_financial_history(cik, ticker)
        print(f"Next earnings for {ticker}: {next_earnings}")
        print(f"Financial history revenue points: {len(financial_history['revenue'])}")
        return jsonify({
            'success':           True,
            'result':            result,
            'company_name':      company_name,
            'form_type':         report_type,
            'filing_date':       filing_date,
            'next_earnings':     next_earnings,
            'financial_history': financial_history
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)