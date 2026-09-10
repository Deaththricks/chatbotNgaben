import json, sys
nb = json.load(open(r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb", encoding="utf-8"))
i = int(sys.argv[1])
out = sys.argv[2]
open(out, "w", encoding="utf-8").write("".join(nb["cells"][i]["source"]))
print("wrote", out, len(nb["cells"][i]["source"]), "lines of source list")
