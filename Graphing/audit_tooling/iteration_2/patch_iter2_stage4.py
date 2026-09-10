"""
Stage 4 of the Iteration 2 patch: MANUAL_RELATION_OVERRIDES additions for
D13 (wrong-subject-via-borrowed-clause cases too risky/uncertain to fix
generally) and D14/D9 (S3334, S3546). Reads _stage3_source.txt, WRITES the
final source back into Knowledge Processing.ipynb cell 51.
"""
import json

STAGE3_PATH = "audit_tooling/iteration_2/_stage3_source.txt"
NB_PATH = "Knowledge Processing.ipynb"
CELL_INDEX = 51


def apply(src, old, new, label):
    count = src.count(old)
    if count == 0:
        raise SystemExit(f"[FAIL] anchor not found for: {label}")
    if count > 1:
        raise SystemExit(f"[FAIL] anchor ambiguous ({count} matches) for: {label}")
    print(f"[ok] {label}")
    return src.replace(old, new, 1)


def main():
    with open(STAGE3_PATH, "r", encoding="utf-8") as f:
        src = f.read()
    original_len = len(src)

    old_overrides_tail = '''    4305: [
        {"subject": "sabda", "subject_label": "KONSEP_FILOSOFIS", "relation": "berasal_dari",
         "object": "akasa", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
        {"subject": "sabda", "subject_label": "KONSEP_FILOSOFIS", "relation": "kembali_ke",
         "object": "akasa", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
    ],
}'''
    new_overrides_tail = '''    4305: [
        {"subject": "sabda", "subject_label": "KONSEP_FILOSOFIS", "relation": "berasal_dari",
         "object": "akasa", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
        {"subject": "sabda", "subject_label": "KONSEP_FILOSOFIS", "relation": "kembali_ke",
         "object": "akasa", "object_label": "KONSEP_FILOSOFIS", "source": "manual_override"},
    ],

    # AUDIT D13 (Iteration 2): "bila pabersihan dilakukan dua atau tiga
    # hari sebelum ngaben..." -- the extractor conflated two distinct
    # ceremonies (pangabenan vs. the pabersihan purification rite held
    # before it); no safe general dependency-based signal found to
    # disambiguate, so hand-captured instead of risking a broader rule.
    1889: [
        {"subject": "pabersihan", "subject_label": None, "relation": "dilakukan",
         "object": "dua atau tiga hari sebelum ngaben", "object_label": None,
         "source": "manual_override"},
    ],

    # AUDIT D13 (Iteration 2): "apakah boleh jenazah itu ditaruh dari
    # samping atau harus dari 'tebenan'?" is phrased as an open QUESTION
    # about a debated convention, not a settled fact -- consistent with
    # this project's "zero relations rather than a wrong/uncertain one"
    # stance (cf. sentence 1298's precedent for reported misconceptions).
    3283: [],

    # AUDIT D7/D13 (Iteration 2): "di samping jenazah, akan ditaruhkan
    # punjung ... yang berisi nasi ..., kopi dan rokok" -- the dependency
    # parser itself mistags the locative "di samping jenazah" as the
    # verb's nsubj:pass (a genuine parser error, not a benefactive-voice
    # pattern the general D7 swap covers), so extraction inherited the
    # error verbatim ("jenazah DITARUHKAN punjung", backwards implying
    # the corpse is placed as an offering). Hand-captured; the contents
    # clause the auto extractor never reached is recovered too.
    3080: [
        {"subject": "punjung", "subject_label": "SARANA_RITUAL",
         "relation": "ditaruhkan_di_samping", "object": "jenazah",
         "object_label": None, "source": "manual_override"},
        {"subject": "punjung", "subject_label": "SARANA_RITUAL", "relation": "berisi",
         "object": "nasi dengan lauknya", "object_label": None, "source": "manual_override"},
        {"subject": "punjung", "subject_label": "SARANA_RITUAL", "relation": "berisi",
         "object": "kopi", "object_label": None, "source": "manual_override"},
        {"subject": "punjung", "subject_label": "SARANA_RITUAL", "relation": "berisi",
         "object": "rokok", "object_label": None, "source": "manual_override"},
    ],

    # AUDIT D9 (Iteration 2): "... (pada saat akhir pabersihan hidup,
    # tangan jenazah/layon ditaruh di dada dengan telapak tangan
    # ditumpuk, diisi sebuah kawangen sebagai simbol sikap amusti
    # karana...)" -- a nested parenthetical clause's temporal-stage
    # phrase ("pabersihan hidup") gets fused as a 4-deep compound chain
    # into what should be a separate subject ("tangan jenazah/layon"), a
    # different mechanism from the semasa/di-masa temporal-nmod fix
    # above (that one is deprel=nmod; this one is deprel=compound, too
    # risky to trim generally without a semantic body-part/stage-noun
    # dictionary). Hand-captured instead.
    3546: [
        {"subject": "tangan jenazah/layon", "subject_label": None, "relation": "diletakkan_di",
         "object": "dada", "object_label": None, "source": "manual_override"},
        {"subject": "tangan jenazah/layon", "subject_label": None, "relation": "ditaruh_dengan",
         "object": "posisi telapak tangan ditumpuk (ditumpangkan)", "object_label": None,
         "source": "manual_override"},
        {"subject": "kawangen", "subject_label": "SARANA_RITUAL", "relation": "melambangkan",
         "object": "sikap amusti karana (seolah-olah layon ikut sembahyang)",
         "object_label": None, "source": "manual_override"},
    ],

    # AUDIT D14 (Iteration 2): "kesembilan galar atau bilah bambu..." --
    # a self-loop by apposition (galar IS bilah bambu, not two things),
    # not catchable by the D14 string-normalization filter (they're
    # different words). The sentence's real content ("bilah bambu nomer
    # 5/di tengah diletakkan terbalik") is too densely embedded to
    # safely reconstruct by rule -- drop rather than assert a guess.
    3334: [],
}'''
    src = apply(src, old_overrides_tail, new_overrides_tail, "D13/D14: MANUAL_RELATION_OVERRIDES additions")

    print(f"\nStage 4 complete. {len(src) - original_len:+d} chars.")

    # ------------------------------------------------------------------
    # Syntax-check the full patched source BEFORE touching the notebook.
    # ------------------------------------------------------------------
    try:
        compile(src, "<cell51-patched>", "exec")
    except SyntaxError as e:
        print(f"\n[FAIL] patched cell 51 has a SyntaxError: {e}")
        with open("audit_tooling/iteration_2/_stage4_source_FAILED.txt", "w", encoding="utf-8") as f:
            f.write(src)
        raise SystemExit(1)
    print("[ok] patched cell 51 source compiles cleanly")

    with open("audit_tooling/iteration_2/_stage4_source.txt", "w", encoding="utf-8") as f:
        f.write(src)

    # ------------------------------------------------------------------
    # Write back into the notebook.
    # ------------------------------------------------------------------
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cell = nb["cells"][CELL_INDEX]
    old_src = "".join(cell["source"])
    print(f"\nOriginal cell 51 length: {len(old_src)}")
    print(f"New cell 51 length:      {len(src)}")

    # Preserve notebook's line-list source format (each element ends with \n
    # except possibly the last).
    lines = src.splitlines(keepends=True)
    cell["source"] = lines

    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print("\n[DONE] Notebook cell 51 updated and written to disk.")


if __name__ == "__main__":
    main()
