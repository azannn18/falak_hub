import subprocess
with open("old_main.py", "w", encoding="utf-8") as f:
    result = subprocess.run(["git", "show", "98c28fcf:backend/main.py"], capture_output=True, text=True, cwd="d:\\coding\\FalakHub")
    f.write(result.stdout)
