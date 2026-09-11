# Glossary Draft — Top 20 Review

**STATUS: APPLIED** — all 16 approved definitions are live in `Graphing/Data/ngaben-merge-cleaned.txt`,
KB rebuilt, Neo4j reloaded. `badan`/`manusia` left undefined (skip). `pangabenan` merged into `ngaben`
(also uncovered and fixed a real bug in `build_kb.py`'s resolver along the way — see below).

Ranked by how often each term is mentioned in the source corpus. Drafts below are
pulled from existing KB facts (`facts.jsonl`) — review/correct before use, don't
treat as authoritative.

**Status:** DRAFT — not yet applied anywhere. Nothing in the bot or KB changes until
you approve and someone copies the approved lines into the source glossary section
(see "How to apply" at the bottom).

## Ready to review — draft definitions (16)

Format matches what the source file's "11. Glosarium" section expects:
`* Term:  Definition.`

- [x ] `* Ngaben:  Upacara pembakaran jenazah (atiwa-tiwa) yang merupakan bagian dari pitra yadnya, bertujuan memusnahkan jasad sawa dan mengembalikannya menjadi pancamahabutha.`
- [x ] `* Jenazah:  Tubuh orang yang telah meninggal, yang dibawa ke setra untuk diupacarai.`
- [x ] `* Mendiang:  Sebutan hormat untuk orang yang telah meninggal.`
- [ x] `* Tirtha:  Air suci yang dimohon dari sulinggih sebagai sarana restu Ida Bhatara.`
- [x ] `* Sawa:  Jenazah dalam konteks upacara, yang dibungkus kain putih sebelum dibakar.`
- [x ] `* Pitra:  Para endahulu, seperti orang tua, nenek moyang dan leluhur yang telah meninggal namun masih bersuksmasarira.`
- [ x] `* Setra:  Kuburan atau tempat penguburan pembakaran jenazah.`
- [x ] `* Kain Putih:  Kain yang membungkus jenazah/layon sebelum upacara.`
- [ x] `* Ngerorasin:  Upacara penyucian pitra, yang dilaksanakan 12 hari setelah ngaben.`
- [ x] `* Yadnya:  Korban suci atau persembahan tulus ikhlas dalam ajaran agama hindu.` ⚠️ *source facts were thin/fragmented — leans on general Hindu-term knowledge more than KB facts, double-check this one especially*
- [ x] `* Upacara Nyiramang Layon:  Upacara memandikan jenazah, menggunakan daun dapdap.`
- [ x] `* Alat Upakara:  Perlengkapan yang digunakan sebagai sarana ritual (mis. adegan).`
- [ x] `* Bhatara:  Sebutan untuk dewa atau Tuhan, atau manifestasi Tuhan yang dipuja.`
- [ x] `* Pepaga:  Balai-balai atau dipan darurat khusus untuk memandikan jenazah.`
- [ x] `* Uang Kepeng:  Uang logam tradisional Bali berlubang tengah, dipakai sebagai sarana ritual.`
- [ x] `* Pabersihan:  Upacara penyucian, juga disebut Pasucian.`

No change needed: `tirta_pangentas` already has a solid, correctly-sourced definition.

## Flagged — not simple definitions, need a decision (4)

- [ ] **`badan`** — SKIP (recommended). Not one term: source text uses it 3 different
  ways ("badan kasar" = physical body in Hindu philosophy, "badan simbol" = a
  symbolic effigy specific to the Swastagni ritual, plus generic "body" elsewhere).
  A single definition would misrepresent it.
- [ ] **`manusia`** — SKIP (recommended). Just the generic word "human/mankind,"
  pulled from one philosophical sentence about karmic debt to the five elements.
  Not actual Ngaben terminology.
- [ ] **`pangabenan`** — MERGE into `ngaben` (recommended), not a separate
  definition. It's just the formal/ceremonial-register noun form of "ngaben"
  itself (e.g. "hari Pangabenan," "tirtha pangabenan").
- [x] **`pabersihan`** — already included above as a draft. Flagging here because
  extraction originally missed it entirely (0 facts); this definition comes
  straight from source text lines 1225–1228, not from `facts.jsonl`.

## How to apply once you've corrected these

1. Edit `Graphing/Data/ngaben-merge-cleaned.txt` — add your approved/corrected
   lines into the "11. Glosarium" section (must stay `* Term:  Definition.`,
   one line each, `*`/`•` bullet required).
2. For `pangabenan` → merge decision: add `"pangabenan": "ngaben"` to
   `force_merge` in `Graphing/kb/entity_resolution.json` instead of writing a
   glossary line for it.
3. Rebuild: `python build_kb.py` (from `Graphing/kb/`).
4. Reload graph: `python Neo4/load_ngaben_to_neo4j.py --source kb` (from `Graphing/`).
5. Restart the Rasa action server so `kb_content.py`/`kb_resolver.py` pick up the
   refreshed `Graphing/kb/` files.
