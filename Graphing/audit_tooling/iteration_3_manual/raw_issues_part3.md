# Raw-source data-quality issues found in S3333-S4340

Checked against `C:\Misc\Work\AI_Chatbot\Graphing\Data\ngaben-merge-cleaned.txt`. Two confirmed genuine issues in the
source document itself (not extraction/segmentation artifacts):

- **Line 3783** (near sentence S4169): "Tirtha Pangentas adalah **seuatu yang memiliki arti yang
  dengan** upacara Pitra Yadnya." â€” grammatically broken; "arti yang dengan" is missing a word,
  most likely meant to be "arti **yang erat** dengan" (has a close relation with) or similar. This
  produces a content-free extraction downstream ("tirtha pangentas ADALAH seuatu") since there's
  nothing coherent to extract. Also note "seuatu" is a typo for "sesuatu" throughout this passage.

- **Line 3789** (near sentence S4177): "Atma Lingga **adalah adalah** mewujudkan Sanghyang Ongkans
  dan Tri Aksara dalam diri yang berstana dalam bathin." â€” the word "adalah" is doubled. This
  directly causes the downstream extraction bug where ADALAH ends up taking a verb phrase
  ("mewujudkan...") as its complement, which is nonsensical. Possible second issue in the same
  sentence, lower confidence: "Sanghyang **Ongkans**" may be intended as "Sanghyang **Ongkara**"
  (Omkara â€” the standard term for the sacred syllable Om) rather than "Ongkans," but this could
  also be a regional/source-specific spelling, not flagging as confirmed.

Recommend fixing both directly in `ngaben-merge-cleaned.txt` (the "adalah adalah" duplication is
unambiguous; the "arti yang dengan" gap needs your judgment on the intended wording) â€” a downstream
`decompose_object`/`derive_raw_relation_label` rule can't recover a triple's real meaning from a
genuinely broken source clause, so these are only fixable at the source.

No other raw-file issues found in this range â€” everything else that looked "weird" traced back to
an extraction bug, not a source-text problem (see `flagtxt_part3.txt` for all of those).
