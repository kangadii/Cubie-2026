
with open('logs/cubie.log', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()
    with open('traceback_extract.txt', 'w', encoding='utf-8') as out:
        out.writelines(lines[-150:])
