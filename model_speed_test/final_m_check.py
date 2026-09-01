import sqlite3
from collections import defaultdict

conn = sqlite3.connect('results/config.db')
conn.row_factory = sqlite3.Row

groups = defaultdict(list)
for r in conn.execute("SELECT name, group_name, enabled FROM models ORDER BY group_name, name").fetchall():
    groups[r['group_name']].append((r['name'], r['enabled']))

for g in sorted(groups):
    en_count = sum(1 for _, e in groups[g] if e)
    print(f"[{g}] {len(groups[g])} models, {en_count} enabled")
    for n, e in groups[g]:
        print(f"  {'ON ' if e else 'off'} {n}")
