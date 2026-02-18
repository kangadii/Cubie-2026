for name in ['logs/uvicorn.log', 'logs/cubie.log']:
    try:
        with open(name, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            print(f"--- {name} ---")
            for line in lines[-150:]:
                print(line.rstrip())
    except Exception as e:
        print(f"Error reading {name}: {e}")
