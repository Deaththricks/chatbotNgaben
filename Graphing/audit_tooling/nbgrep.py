import json, sys, re

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
nb = json.load(open(NB, encoding="utf-8"))

mode = sys.argv[1]

if mode == "list":
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        first = src.strip().splitlines()[0] if src.strip() else ""
        print(f"[{i}] {c['cell_type']:8} {len(src):7d}  {first[:110]}")

elif mode == "grep":
    pat = re.compile(sys.argv[2], re.I)
    for i, c in enumerate(nb["cells"]):
        lines = "".join(c.get("source", [])).splitlines()
        for ln, line in enumerate(lines):
            if pat.search(line):
                print(f"cell {i} L{ln}: {line}")

elif mode == "cell":
    i = int(sys.argv[2])
    src = "".join(nb["cells"][i].get("source", []))
    lines = src.splitlines()
    a = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    b = int(sys.argv[4]) if len(sys.argv) > 4 else len(lines)
    for ln in range(a, min(b, len(lines))):
        print(f"{ln:5d}  {lines[ln]}")

elif mode == "context":
    # grep with N lines context inside whichever cell
    pat = re.compile(sys.argv[2], re.I)
    ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    for i, c in enumerate(nb["cells"]):
        lines = "".join(c.get("source", [])).splitlines()
        for ln, line in enumerate(lines):
            if pat.search(line):
                print(f"--- cell {i} around L{ln} ---")
                for j in range(max(0, ln-ctx), min(len(lines), ln+ctx+1)):
                    print(f"{j:5d}  {lines[j]}")
                print()
