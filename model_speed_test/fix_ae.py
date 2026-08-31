path = 'web/report_generator.py'
with open(path, encoding='utf-8') as f:
    c = f.read()

old = "autoescape=select_autoescape(enabled_extensions=()),"
new = "autoescape=select_autoescape(default_for_string=True, default=True),"

if old in c:
    c = c.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print('autoescape enabled')
else:
    print('not found')
