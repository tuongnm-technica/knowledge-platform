import sys
sys.path.insert(0, ".")

from connectors.fileserver.smb_client import SMBClient

client = SMBClient()

print("Testing SMB connection...")
ok = client.test_connection()
print(f"Connection: {'✅ OK' if ok else '❌ FAILED'}")

if ok:
    files = client.list_files()
    print(f"\nFound {len(files)} files:")
    for f in files[:15]:
        print(f"  - [{f['ext']}] {f['path']} ({f['size']//1024}KB)")