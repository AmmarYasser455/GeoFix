import os
import shutil

dirs = ["assets", "docs"]
for d in dirs:
    os.makedirs(d, exist_ok=True)

files = {
    "geof4.png": "assets/geof4.png",
    "geof42.png": "assets/geof42.png",
    "plan.md": "docs/plan.md"
}

for src, dest in files.items():
    if os.path.exists(src):
        shutil.move(src, dest)
        print(f"Moved {src} to {dest}")
    else:
        print(f"Skipped {src} (not found)")
