f = open('app.py', 'r', encoding='utf-8').read()
old = '''        "10-Q": [
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
        ],'''
new = '''        "10-Q": [
            "RESULTS OF OPERATIONS",
            "CONSOLIDATED STATEMENTS OF OPERATIONS",
            "CONSOLIDATED STATEMENTS OF INCOME",
            "STATEMENTS OF OPERATIONS",
            "STATEMENTS OF INCOME",
            "Financial Statements",
        ],
        "10-K": [
            "RESULTS OF OPERATIONS",
            "CONSOLIDATED STATEMENTS OF OPERATIONS",
            "CONSOLIDATED STATEMENTS OF INCOME",
            "STATEMENTS OF OPERATIONS",
            "STATEMENTS OF INCOME",
            "Financial Statements",
        ],'''
if old in f:
    f = f.replace(old, new)
    open('app.py', 'w', encoding='utf-8').write(f)
    print('done')
else:
    print('not found - checking app.py content...')
    print(f[1000:2000])