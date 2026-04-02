import sys
import os

sys.path.insert(0, os.getcwd())

try:
    print("Trying to import tests.api.test_workflow_routes...")
    import tests.api.test_workflow_routes
    print("Import successful!")
except Exception as e:
    import traceback
    print("Import failed with error:")
    traceback.print_exc()
