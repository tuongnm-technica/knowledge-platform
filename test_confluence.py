import sys
sys.path.insert(0, ".")

from connectors.confluence.confluence_client import ConfluenceClient

client = ConfluenceClient()

# Test kết nối
print("Testing connection...")
ok = client.test_connection()
print(f"Connection: {'✅ OK' if ok else '❌ FAILED'}")

if ok:
    # Lấy danh sách spaces
    spaces = client.get_spaces()
    print(f"\nFound {len(spaces)} spaces:")
    for s in spaces[:5]:
        print(f"  - [{s['key']}] {s['name']}")