f = open('app.py', 'r', encoding='utf-8').read()
old = '''        revenue_data = []
        for key in revenue_keys:
            revenue_data = extract_quarterly(key)
            if revenue_data:
                break
        income_data = []
        for key in income_keys:
            income_data = extract_quarterly(key)
            if income_data:
                break'''
new = '''        # 最新データがあるキーを選択
        def best_data(keys):
            best = []
            for key in keys:
                data = extract_quarterly(key)
                if data and (not best or data[-1]["period"] > best[-1]["period"]):
                    best = data
            return best

        revenue_data = best_data(revenue_keys)
        income_data = best_data(income_keys)'''
if old in f:
    f = f.replace(old, new)
    open('app.py', 'w', encoding='utf-8').write(f)
    print('done')
else:
    print('not found')