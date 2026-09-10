import json, shutil, datetime

NB = r"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb"
ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
backup = rf"C:\Misc\Work\AI_Chatbot\Graphing\Knowledge Processing.ipynb.bak_relfix_{ts}"
shutil.copy(NB, backup)
print("backup:", backup)

nb = json.load(open(NB, encoding="utf-8"))
src = "".join(nb["cells"][51]["source"])

old = '''    # different words). The sentence's real content ("bilah bambu nomer
    # 5/di tengah diletakkan terbalik") is too densely embedded to
    # safely reconstruct by rule -- drop rather than assert a guess.
    3334: [],
}'''

new = '''    # different words). The sentence's real content ("bilah bambu nomer
    # 5/di tengah diletakkan terbalik") is too densely embedded to
    # safely reconstruct by rule -- drop rather than assert a guess.
    3334: [],

    # AUDIT D9 (Iteration 3, Stage 5): section-heading-as-subject bug, still
    # no safe general signal after a second look (Iteration 2 already found
    # none) -- the parser attaches a heading-style noun ("itik-itik,",
    # "kwangen jeriji:") as nsubj:pass of an unrelated following clause's
    # verb. Targeted overrides using flag.txt's own confirmed content.
    3604: [
        {"subject": "jempol jari tangan (kedua ibu jari)", "subject_label": None,
         "relation": "diikat_dengan",
         "object": "tali benang tukelan (benang tenun bali) berwarna putih",
         "object_label": None, "source": "manual_override"},
        {"subject": "jempol jari kaki", "subject_label": None,
         "relation": "diikat_dengan", "object": "tali benang tukelan",
         "object_label": None, "source": "manual_override"},
    ],
    3973: [
        {"subject": "jempol jari tangan (kedua ibu jari)", "subject_label": None,
         "relation": "diikat_dengan", "object": "tali benang tukelan",
         "object_label": None, "source": "manual_override"},
    ],
    # AUDIT D9 (Iteration 3, Stage 5): same heading-as-subject bug produces
    # one junk relation ("kwangen jeriji SETELAH pelaksanaan eteh-eteh
    # pabersihan mati") alongside two otherwise-good placement facts; the
    # override replaces all three with just the two good ones (reconstructed
    # from the real parse) so the junk one can't resurface.
    3733: [
        {"subject": "kwangen jeriji", "subject_label": None,
         "relation": "ditaruh_di", "object": "telapak tangan",
         "object_label": None, "source": "manual_override"},
        {"subject": "kwangen jeriji", "subject_label": None,
         "relation": "ditaruh_di", "object": "telapak kaki",
         "object_label": None, "source": "manual_override"},
    ],
    # AUDIT D16/N12 (Iteration 3, Stage 5, opportunistic): sentence's main
    # point (needle and iron nail placed on the corpse's arm before wrapping)
    # produced zero triples in the auto extraction; the only surviving
    # relation was a low-value SEBELUM fragment. Override with the real
    # content per flag.txt.
    3760: [
        {"subject": "jarum (jaum)", "subject_label": None,
         "relation": "ditaruh_di", "object": "lengan jenazah",
         "object_label": None, "source": "manual_override"},
        {"subject": "besi paku", "subject_label": None,
         "relation": "ditaruh_di", "object": "lengan jenazah",
         "object_label": None, "source": "manual_override"},
    ],
}'''

assert src.count(old) == 1, f"expected exactly 1 match, found {src.count(old)}"
src = src.replace(old, new)

nb["cells"][51]["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("patched.")
