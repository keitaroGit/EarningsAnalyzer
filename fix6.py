f = open('app.py', 'r', encoding='utf-8').read()
old = '''    system_prompt = f"""You are an expert financial analyst specializing in SEC filings.
Analyze the provided {form_type} ({form_desc}) and respond in {lang_label}.
IMPORTANT RULES:
- Always extract and state specific dollar amounts, percentages, and figures when available
- Never say "figures are not available" or "not included in the text" - instead summarize what IS available
- If exact numbers are not in the text, use the directional information (growth%, YoY trends) that is available
- Be concise and factual
Return ONLY a JSON object with no additional text or code blocks:'''
new = '''    system_prompt = f"""You are an expert financial analyst specializing in SEC filings.
Analyze the provided {form_type} ({form_desc}) and respond ENTIRELY in {lang_label}. ALL text in the JSON values must be in {lang_label}. Do not use any other language.
IMPORTANT RULES:
- Always extract and state specific dollar amounts, percentages, and figures when available
- Never say "figures are not available" or "not included in the text" - instead summarize what IS available
- If exact numbers are not in the text, use the directional information (growth%, YoY trends) that is available
- Be concise and factual
Return ONLY a JSON object with no additional text or code blocks:'''
if old in f:
    f = f.replace(old, new)
    open('app.py', 'w', encoding='utf-8').write(f)
    print('done')
else:
    print('not found')