from pathlib import Path
lines = Path('handlers/admin_handlers.py').read_text(encoding='utf-8').splitlines()
for i in range(1700, 1740):
    if i >= len(lines):
        break
    print(f"{i+1}: {lines[i].encode('unicode_escape').decode()}")
