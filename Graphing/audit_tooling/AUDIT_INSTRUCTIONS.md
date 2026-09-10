# Ngaben relation-extraction audit â€” shared instructions

## Context
`C:\Misc\Work\AI_Chatbot\Graphing` is an Indonesian/Balinese NLP pipeline over a corpus about **Ngaben** (Balinese
Hindu cremation ritual). The final stage does rule-based **relation extraction**: each record is a
triple `subject --[RELATION]--> object` with `object_type` ENTITY or LITERAL and a `source`
(`dependency_rule`, `object_decomposition`, `manual_override`).

The user has hand-audited 50 sample triples in `C:\Misc\Work\AI_Chatbot\Graphing\flag.txt` and wants the SAME scrutiny
applied to every remaining triple. Your job: audit one chunk.

## Your input
A bundle file (path given in your task) containing, per sentence: `TEXT`, `NER` entities,
the CoNLLU dependency `PARSE`, and the extracted `RELATIONS` (indexed `[0]`, `[1]`, ...).
Also read `C:\Misc\Work\AI_Chatbot\Graphing\flag.txt` in full first â€” it is the rubric: it shows the kinds of
problems that matter and the fix style the user wants.

## What the user wants (from flag.txt closing paragraph)
> "scrutinize everything. dont understand a word or a sentence? translate it yourself. an
> extraction feels weird? can you fix it or should we drop it. whatever it takes to make the
> triple absolutely the best of the best with the method we are doing right now ... return to me
> a report of all the issues you see, and how to fix them."

## Failure modes to hunt for (derived from the 50 flagged samples)
1. **Wrong subject** â€” the triple's subject is not the real-world entity the predicate applies to
   (e.g. a ceremony *name* used as subject when the thing acted on is the ashes/corpse).
2. **Wrong object** â€” parser grabbed the wrong token; object should be a different noun in the
   sentence, or a more/less specific span.
3. **Nonsense triple** â€” object or predicate is a function word, a verb stem, a fragment, or
   otherwise says nothing ("banten ADALAH menjadi", "gedarba ADALAH berbentuk").
4. **Source-text bleed** â€” the citation/source of a statement captured as if it were the entity
   ("banten DIKENAL_SEBAGAI lontar yama purwa tatwa" â€” that lontar is the *source*, not an alias).
5. **Wrong relation label** â€” predicate misrepresents the sentence. Note Balinese: `ring` = "di/pada"
   â†’ "put at / offered to"; `membujur` (lie oriented) â‰  `menuju` (head toward); a passive
   "offered/haturkan" should read as "dipersembahkan kepada" / "offered to" not "LAINNYA".
6. **Lost nuance / too terse** â€” triple is technically true but strips the qualifier that carried
   the meaning ("sasih" vs "sasih yang baik untuk pitra yadnya"; "jenis" vs "beberapa jenis").
7. **Missing coordinate member** â€” sentence lists two+ items, only one extracted (e.g. "sasih kasa
   **dan kapitu**" â†’ only "kasa" kept; want both).
8. **Under-extraction** â€” sentence clearly carries more triples than were pulled. Propose the
   missing ones in `subject | predicate | object` form. Be generous here â€” the user repeatedly
   asks for "more extraction".
9. **Drop candidates** â€” sentence too broken / segmentation-mangled / meaningless to salvage.
10. **Balinese sentences** â€” many S-ids in later chunks are pure Balinese offering lists
    (`banten X ring Y, Z, lan W`). Translate them. `saha`/`lan` = "dan" (and); `sane` = "yang";
    `ring` = "di/pada/kepada"; `munggah ring` = "the offerings that go up to / for";
    `nuwur` = "memohon" (request). These list-sentences currently get `LAINNYA` a lot â€” judge
    whether a real predicate ("dipersembahkan di/kepada", "diperlukan untuk") fits.

## Method â€” for EVERY relation in your chunk
- Read the TEXT. If any word is unfamiliar (Balinese ritual vocab), translate it â€” state your
  gloss in the finding.
- Check subject, predicate, object against the parse and against meaning.
- Decide a verdict: **KEEP** / **FIX** / **DROP** / (plus) **ADD** for missing triples.
- Only report KEEPs you are NOT flagging if they're borderline-but-ok worth a note; otherwise
  don't list clean KEEPs.
- For sentences already covered in flag.txt, the user's verdict there is authoritative â€” you may
  skip re-deriving them, but if you spot an AD'l issue on that sentence, note it.

## Output format â€” return EXACTLY this, nothing else
A markdown report:

```
# Chunk N audit (S___..S___)

## FIX  (triple is salvageable â€” give the corrected triple)
- **S123 [1]**  current: `subj | REL | obj`
  fix: `subj | REL | obj`
  why: <one-two lines, include translation if needed>

## DROP  (triple should be removed)
- **S123 [0]**  `subj | REL | obj`
  why: <...>

## ADD  (missing triples the sentence supports)
- **S123**  `subj | predicate | obj`  (+ more)
  why: <...>

## NOTE  (borderline / systemic observation, no single fix)
- **S123**  <...>

## Chunk stats
FIX: n   DROP: n   ADD: n   sentences reviewed: n
```

Be thorough and concrete. Translate freely. This is a language-judgment task â€” spend the effort.
