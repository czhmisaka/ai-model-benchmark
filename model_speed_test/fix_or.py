path = 'web/app.py'
with open(path, encoding='utf-8') as f:
    c = f.read()

old = '            max_conc = int((config.get("concurrency", {}) or {}).get("max_concurrent", 3) or 3)'
new = '            raw_mc = (config.get("concurrency", {}) or {}).get("max_concurrent", 3)
            max_conc = int(raw_mc) if raw_mc is not None else 3'

if old in c:
    c = c.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print('or-3 removed')
else:
    print('not found')
