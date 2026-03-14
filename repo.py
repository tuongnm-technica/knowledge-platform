import os

ignore = {"node_modules", ".git", "__pycache__"}

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ignore]
    level = root.count(os.sep)
    indent = " " * 4 * level
    print(f"{indent}{os.path.basename(root)}/")
    for f in files:
        print(f"{indent}    {f}")