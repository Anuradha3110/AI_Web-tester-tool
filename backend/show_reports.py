import sqlite3

conn = sqlite3.connect("web_tester.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 60)
print("TEST RUNS")
print("=" * 60)
cur.execute(
    "SELECT id, url, goal, final_verdict, total_steps, passed_steps, failed_steps, duration, created_at "
    "FROM test_runs ORDER BY created_at DESC"
)
runs = cur.fetchall()
if not runs:
    print("  No test runs found yet.")
for row in runs:
    r = dict(row)
    verdict_icon = "PASSED" if r["final_verdict"] == "PASSED" else "FAILED" if r["final_verdict"] == "FAILED" else r["final_verdict"]
    print(f"\n  ID      : {r['id']}")
    print(f"  URL     : {r['url']}")
    print(f"  Goal    : {r['goal']}")
    print(f"  Verdict : {verdict_icon}")
    print(f"  Steps   : {r['total_steps']} total | {r['passed_steps']} passed | {r['failed_steps']} failed")
    print(f"  Duration: {round(r['duration'], 2)}s" if r['duration'] else "  Duration: -")
    print(f"  Date    : {r['created_at']}")

print("\n" + "=" * 60)
print("TEST STEPS (latest run)")
print("=" * 60)
if runs:
    latest_id = dict(runs[0])["id"]
    cur.execute(
        "SELECT step_number, action, target, value, status, reasoning, error_message "
        "FROM test_steps WHERE test_run_id = ? ORDER BY step_number",
        (latest_id,),
    )
    steps = cur.fetchall()
    if not steps:
        print("  No steps recorded.")
    for s in steps:
        s = dict(s)
        print(f"\n  Step {s['step_number']}: [{s['action'].upper()}]")
        print(f"    Target   : {s['target']}")
        if s["value"]:
            print(f"    Value    : {s['value']}")
        print(f"    Status   : {s['status']}")
        print(f"    Reasoning: {s['reasoning']}")
        if s["error_message"]:
            print(f"    Error    : {s['error_message']}")

conn.close()
