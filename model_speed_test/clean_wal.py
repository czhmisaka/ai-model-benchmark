import sqlite3

conn = sqlite3.connect('results/test_results.db')
conn.row_factory = sqlite3.Row
try:
    conn.execute("DELETE FROM test_results WHERE group_id = 'wal-test-001'")
    conn.execute("DELETE FROM test_groups WHERE group_id = 'wal-test-001'")
    conn.commit()
    print('wal-test-001 cleaned')
except Exception as e:
    print('clean failed:', e)
finally:
    conn.close()
