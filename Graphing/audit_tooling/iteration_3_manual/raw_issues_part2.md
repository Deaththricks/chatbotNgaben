# Raw-source data-quality issues — part 2 (S2364-S3332)

None found. Every extraction problem in this range traces to the extractor (wrong subject/relation,
clause-stripping, coordinate-list truncation, garbled decomposition), not to a defect in
`Data/ngaben-merge-cleaned.txt` itself. Some source sentences are genuinely long/run-on
(S2604, S2988, S3001) or lean on rhetorical questions (S2988) or mixed Balinese/Indonesian
terminology (S3091's "atma baan nyilih") — these make extraction harder but aren't data corruption,
just the author's original writing style. Nothing here needs a raw-file edit.
