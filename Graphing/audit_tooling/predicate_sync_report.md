# Predicate sync — what's actually stale, and how to fix it

## What I found

The notebook's relation cascade deliberately emits an **open tail** of natural Indonesian
predicates — **264 distinct predicate strings** in the current run (916 rows). That's by design
(`relation_map.json`'s own comment says so; `normalize.py` has a `VOICED_PREDICATE` regex meant to
wave most of them through). So "sync the 43 pending predicates" undersold it — and hand-listing
templates for 200+ predicates would be the wrong fix anyway.

Three downstream configs are stale against that 264:

| Config | State | Effect |
|---|---|---|
| `Neo4/relation_map.json` + `CANONICAL_RELATIONS` in `normalize.py` | only ~9 of the 264 get remapped; **70 hit the "still-unmapped, review" log** | Not dropped — they pass through uppercased. But true synonyms (`MERUPAKAN`/`ADALAH`, `DITARUH_DI`/`DILETAKKAN_DI`, `DIMASUKKAN_KE`/`DIMASUKKAN_KE_DALAM`, `MEMPERGUNAKAN`/`MENGGUNAKAN`, …) stay as **separate edge types** → noisier graph |
| `kb/relation_phrases.json` | covers 56 predicates; **208 of the 264 final predicates have no entry** | **The real bug — see below** |
| `HIGH_PREDS` / `MED_PREDS` in `build_kb.py` | ~40 predicates; most of the open tail absent | Open-tail facts can't reach HIGH confidence even when clean |

## The real bug (not cosmetic)

`build_kb.py` fact stage, per row (`build_kb.py:526`):

```python
ok_prep  = set(phrases.get(pred, {}).get("ok_prep", []))          # {} for any of the 208
prep_bad = prep in PREP_BEFORE_OBJ and prep not in ok_prep and prep is not None
...
if prep_bad: reasons.append(...)          # -> conf = "LOW", row goes to review_queue.jsonl
```

Most open-tail predicates are locatives/instrumentals — `DITARUH_DI`, `DIMASUKKAN_KE_DALAM`,
`DISUCIKAN_DENGAN`, `DIPERCIKKAN_PADA`, `DIOLESKAN_DI` … — whose object **naturally** follows its
preposition in the source sentence. With no `ok_prep` list, every one of those trips `prep_bad`
and gets forced to **LOW confidence + dumped to the review queue**, even when both endpoints
resolve cleanly. That's a large slice of otherwise-good auto facts.
(`source == "manual_override"` rows are exempt — they're hard-coded HIGH — so the /009 fixes
themselves are unaffected; it's the auto-extracted rows that bleed.)

Second effect: the NL render falls back to `"{s} " + pred.lower() + " {o}"` →
`"kajang dilipat_di jenazah"` — underscores leak into the sentence a chatbot would read.

## Proposed fix

### Part A — canonical merges (needs your sign-off on the list)

~25 true synonyms/variants folded into `relation_map.json` + `CANONICAL_RELATIONS`. Draft list
(you edit before I apply):

| merge these | → into | note |
|---|---|---|
| `MERUPAKAN` | `ADALAH` | |
| `DITARUH_DI`, `DITEMPATKAN_DI`, `DITARUH` (bare) | `DILETAKKAN_DI` | |
| `DIMASUKKAN`, `DIMASUKKAN_KE` | `DIMASUKKAN_KE_DALAM` | |
| `MEMPERGUNAKAN`, `DIPERGUNAKAN_SEBAGAI` | `MENGGUNAKAN` | |
| `MENYERUPAI` | `MELAMBANGKAN` | or `DIPERLAKUKAN_SEPERTI` — your call |
| `TERGOLONG_BERSAMA`, `JENIS_DARI` | `BAGIAN_DARI` | (`TERGOLONG`→`BAGIAN_DARI` already exists) |
| `SEPADAN_DENGAN`, `DIPERLAKUKAN_SAMA_DENGAN` | `SAMA_DENGAN` | keep `SAMA_DENGAN` as a new canonical |
| `MEMILIKI_ALIAS` | `DIKENAL_SEBAGAI` | |
| `NAIK`, `NAIK_KE` | `MENUJU` | |
| `MEMOHON`, `MEMOHON`… `DIMOHONKAN_DARI` | `DIMOHON_DARI` | |
| `MENDAPATKAN`, `MENGAMBIL` | `MEMPEROLEH` | ⚠ check direction |
| `TENTANG` | drop (already `prep_fatal`) | |
| `MEMPEROLEH_DARI` | keep (it's real) | just add to canonical set |
| `DIGILING_DI`, `DIGILING_DI_ATAS` | `DIGILING` + keep locative? | your call — I lean keep `DIGILING_DI_ATAS` (S2947 /009), merge bare `DIGILING_DI`→it |

Everything else stays open-tail.

### Part B — kill the `prep_bad` false-positives for the whole open tail (the actual fix)

Add a **derived-default** function to `build_kb.py` so a predicate with no `relation_phrases.json`
entry gets a sane `ok_prep` + `template` **from its own morphology** instead of `{}`:

- suffix `_DI` → `ok_prep {di, pada, ke, atas}`, `"{s} <verb> di {o}"`
- suffix `_KE` / `_KE_DALAM` → `{ke}` / `{ke dalam, ke}`
- suffix `_DENGAN` → `{dengan}`
- suffix `_DARI` → `{dari}`
- suffix `_UNTUK` → `{untuk, bagi}`; `_KEPADA`/`_PADA` → `{kepada, pada, ke}`; `_SEBAGAI` → `{sebagai, selaku}`
- suffix `_SEBELUM`/`_SETELAH`/`_SAAT` → temporal preps
- bare `DI…`/`TER…` passive, no suffix → loose `{dengan, oleh, di, pada}`
- bare `ME…`/`BER…` active, no suffix → `ok_prep []` (direct object, no prep expected)
- template: verb rendered with `_`→space, lowercased

`relation_phrases.json` then stays as the **hand-tuned override file** for the 56 it already
covers — nothing there changes. ~35 lines, deterministic, no per-predicate data entry.

### Part C — regen + measure

Re-run `Neo4/normalize.py` then `kb/build_kb.py`; report the before/after on
review-queue size, HIGH/MED/LOW split, and distinct-relation count. Add the 3 /009 predicates
+ any clearly-reliable open-tail ones to `HIGH_PREDS`/`MED_PREDS` based on that.

## Your call

1. **Full** (A + B + C) — fixes the review-queue bleed. ~Recommended.
2. **Merges only** (A + C) — tidier graph, but the KB review-queue inflation stays.
3. Edit the Part A merge list first, then I proceed.

Nothing here touches the notebook or `Results/Final/` — it's all in `Neo4/` and `kb/`, re-runnable.

---

## DONE — 2026-09-07

Full fix (A + B + C) applied and both artifacts regenerated.

**Part A — `Neo4/relation_map.json` + `normalize.py`:**
- 18 new synonym merges added to `relation_map.json` (`MERUPAKAN`/`JUGA_ADALAH`→`ADALAH`,
  `DITARUH`/`DITARUH_DI`/`DITEMPATKAN_DI`→`DILETAKKAN_DI`, `DIMASUKKAN`/`DIMASUKKAN_KE`→
  `DIMASUKKAN_KE_DALAM`, `MEMPERGUNAKAN`→`MENGGUNAKAN`, `DIPERGUNAKAN_SEBAGAI`→`DIPAKAI_UNTUK`,
  `MENYERUPAI`→`MELAMBANGKAN`, `TERGOLONG_BERSAMA`/`JENIS_DARI`→`BAGIAN_DARI`,
  `SEPADAN_DENGAN`/`DIPERLAKUKAN_SAMA_DENGAN`→`SAMA_DENGAN`, `MEMILIKI_ALIAS`→`DIKENAL_SEBAGAI`,
  `NAIK`/`NAIK_KE`→`MENUJU`, `TENTANG`→`LAINNYA`, `DIGILING_DI`→`DIGILING_DI_ATAS`).
- Held back (direction-risky, left as open-tail): `MENDAPATKAN`/`MENGAMBIL`→`MEMPEROLEH`, the
  `MEMOHON`/`DIMOHONKAN_*` cluster.
- `normalize.py`: `VOICED_PREDICATE` regex loosened to accept multi-segment voiced predicates
  (`^(DI|TER|ME…|BER)[A-Z]{2,}(_[A-Z]{2,})*$`); ~20 non-voiced-prefix open-tail predicates added
  to `CANONICAL_RELATIONS`. Result: **"still-unmapped, review" log went from 70 → 0**.
- Distinct relations after normalize: **264 → 234**.

**Part B — `kb/build_kb.py`:** added `derived_phrase_spec(pred)` / `phrase_spec(pred, phrases)` —
a predicate with no `relation_phrases.json` entry now gets a morphology-derived `ok_prep` +
template (suffix `_DI`→di/pada/ke/atas, `_DENGAN`→dengan/oleh, passive `DI…`→loose locative set,
active `ME…`/`BER…`→bare object, …). `relation_phrases.json` unchanged — still the hand-tuned
override for its 56.

**Part C — regenerated `Neo4/relation_results_ngaben.normalized.json` + all of `kb/`:**

| metric | before (stale, pre-/009) | after |
|---|---|---|
| entity edges | 290 | 305 |
| HIGH / MED / LOW | 84 / 170 / 36 | **191 / 103 / 11** |
| facts.jsonl (HIGH+MED) | 254 | **294** |
| review_queue.jsonl | 50 | **24** |
| NL renders with an `under_scored` predicate | many | **0** |

review_queue is now almost entirely legitimate (13 fragment-entities, 6 decomposed sub-relations
with an unresolved endpoint, 4 with neither endpoint known); only **2** rows still trace to a
prep mismatch (`DINAIKKAN_KE`+"di", `BERISI`+"dengan") and both look like real signal worth a
glance. (Part of the HIGH jump is also the 27 /009 `manual_override` rows, which score HIGH by
rule — but the LOW 36→11 and the underscore-NL fix are the config change.)

**Still manual (needs a running Neo4j, which I can't reach):** `python Neo4/load_ngaben_to_neo4j.py`
then re-export the KG SVG from Neo4j Browser. `kb/build_report.txt.pre_predsync` kept as the
before snapshot.
