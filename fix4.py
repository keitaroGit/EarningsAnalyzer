f = open('app.py', 'r', encoding='utf-8').read()
old = '''        def extract_quarterly(key):
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
            return quarterly[-8:] if len(quarterly) >= 2 else []'''
new = '''        def extract_quarterly(key):
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
            return quarterly[-8:] if len(quarterly) >= 2 else []'''
if old in f:
    f = f.replace(old, new)
    open('app.py', 'w', encoding='utf-8').write(f)
    print('done')
else:
    print('not found')