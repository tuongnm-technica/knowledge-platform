import sys
sys.path.insert(0, ".")

from connectors.jira.jira_client import JiraClient

client = JiraClient()

print("Testing Jira connection...")
ok = client.test_connection()
print(f"Connection: {'✅ OK' if ok else '❌ FAILED'}")

if ok:
    projects = client.get_projects()
    print(f"\nFound {len(projects)} projects:")
    for p in projects[:10]:
        print(f"  - [{p['key']}] {p.get('name', '')}")