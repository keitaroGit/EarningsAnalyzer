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
    """書類種別ごとに複数セクションを狙い撃ちして抽出・結合"""
    MAX_CHARS = 25000  # セクションごとの最大文字数
    text_upper = raw_text.upper()

    if form_type in ("10-Q", "10-K"):
        # セクション1: Results of Operations（経営分析・前年比説明）
        results_keywords = [
            "RESULTS OF OPERATIONS",
            "MANAGEMENT'S DISCUSSION",
        ]
        # セクション2: 財務諸表（具体的な数字）
        financial_keywords = [
            "CONSOLIDATED STATEMENTS OF OPERATIONS",
            "CONSOLIDATED STATEMENTS OF INCOME",
            "CONDENSED CONSOLIDATED STATEMENTS",
            "STATEMENTS OF OPERATIONS",
            "STATEMENTS OF INCOME",
        ]

        section1 = ""
        for kw in results_keywords:
            idx = text_upper.find(kw)
            if idx != -1:
                start = max(0, idx - 200)
                end = min(len(raw_text), idx + MAX_CHARS)
                section1 = raw_text[start:end]
                print(f"Section1 found: '{kw}' at {idx}, {len(section1)} chars")
                break

        section2 = ""
        for kw in financial_keywords:
            idx = text_upper.find(kw)
            if idx != -1:
                start = max(0, idx - 200)
                end = min(len(raw_text), idx + MAX_CHARS)
                section2 = raw_text[start:end]
                print(f"Section2 found: '{kw}' at {idx}, {len(section2)} chars")
                break

        if section1 or section2:
            combined = ""
            if section2:
                combined += "=== FINANCIAL STATEMENTS ===\n" + section2 + "\n\n"
            if section1:
                combined += "=== RESULTS OF OPERATIONS ===\n" + section1
            print(f"Combined text: {len(combined)} chars")
            return combined

        # 見つからない場合は先頭から
        print(f"No keywords found, using first 50000 chars")
        return raw_text[:50000]

    elif form_type == "8-K":
        keywords = [
            "Item 2.02",
            "ITEM 2.02",
            "Results of Operations and Financial Condition",
            "RESULTS OF OPERATIONS",
            "Item 2.01",
            "Item 1.01",
        ]
        for kw in keywords:
            idx = text_upper.find(kw.upper())
            if idx != -1:
                start = max(0, idx - 200)
                end = min(len(raw_text), idx + MAX_CHARS * 2)
                extracted = raw_text[start:end]
                print(f"8-K keyword '{kw}' found at {idx}, {len(extracted)} chars")
                return extracted
        return raw_text[:50000]

    elif form_type == "DEF 14A":
        keywords = [
            "EXECUTIVE COMPENSATION",
            "Executive Compensation",
            "COMPENSATION DISCUSSION",
            "Compensation Discussion",
            "SUMMARY COMPENSATION TABLE",
            "Summary Compensation Table",
        ]
        for kw in keywords:
            idx = text_upper.find(kw.upper())
            if idx != -1:
                start = max(0, idx - 200)
                end = min(len(raw_text), idx + MAX_CHARS * 2)
                extracted = raw_text[start:end]
                print(f"DEF14A keyword '{kw}' found at {idx}, {len(extracted)} chars")
                return extracted
        return raw_text[:50000]

    return raw_text[:50000]


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
            extracted = extract_relevant_text(text, target_form)
            return extracted, filing_date
    raise Exception(f"{target_form} filing not found.")


def get_financial_history(cik, ticker):
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        facts = resp.json()
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        revenue_keys = [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
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
            # 期間ごとに最小値を選択（四半期単体の値を優先）
            period_dict = {}
            for item in usd:
                form = item.get("form", "")
                if form in ("10-Q", "10-K"):
                    end = item.get("end", "")
                    val = item.get("val", 0)
                    start = item.get("start", "")
                    if end:
                        # 同じ期間なら値が小さい方（四半期単体）を優先
                        if end not in period_dict or val < period_dict[end]["value"]:
                            period_dict[end] = {"period": end, "value": val, "form": form, "start": start}
            quarterly = list(period_dict.values())
            quarterly.sort(key=lambda x: x["period"])
            return quarterly[-8:] if len(quarterly) >= 2 else []
        # 最新データがあるキーを選択
        def best_data(keys):
            best = []
            for key in keys:
                data = extract_quarterly(key)
                if data and (not best or data[-1]["period"] > best[-1]["period"]):
                    best = data
            return best

        revenue_data = best_data(revenue_keys)
        income_data = best_data(income_keys)
        def to_billions(items):
            return [{"period": item["period"], "value": round(item["value"] / 1_000_000_000, 2), "form": item["form"]} for item in items]
        return {"revenue": to_billions(revenue_data), "net_income": to_billions(income_data), "currency": "USD Billions"}
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
Analyze the provided {form_type} ({form_desc}) and respond ENTIRELY in {lang_label}. ALL text in the JSON values must be in {lang_label}. Do not use any other language.
IMPORTANT RULES:
- Always extract and state specific dollar amounts, percentages, and figures when available
- Never say "figures are not available" or "not included in the text" - instead summarize what IS available
- If exact numbers are not in the text, use the directional information (growth%, YoY trends) that is available
- Be concise and factual
Return ONLY a JSON object with no additional text or code blocks:
{{
    "revenue_profit_summary": "Revenue and profit summary with specific numbers and YoY comparison. Include quarterly and cumulative figures if available.",
    "management_topics": "Key management statements and topics as bullet points",
    "investor_summary": "One or two sentence summary for investors",
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