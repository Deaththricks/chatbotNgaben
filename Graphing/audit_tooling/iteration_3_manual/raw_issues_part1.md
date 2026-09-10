# Raw-source data-quality issues found — Part 1 (S1482-S2363)

- **Near S1732** (`upadesa yang dalam masyarakat kita lebih dikenal dengan nama upanisad, menurut
  para ahli memang berarti "bisikan dang guru" kepada sisia atau juga berarti "tatwa pengarahan
  hidup." tentang acara yang pelik ini, satu hal perlu kita catat, bahwa`): this sentence cuts off
  mid-clause at "bahwa" with no continuation — looks like a sentence-segmentation boundary landed
  in the wrong place, splitting what should be one sentence (or dropping its second half) rather
  than a problem with the source document's actual prose. Worth checking `ngaben-merge-cleaned.txt`
  around this passage to see whether the intended continuation exists in the raw file and just
  didn't survive segmentation, or whether the source itself trails off there (e.g. a scan/OCR
  artifact upstream of this cleaned file). I did not have time to trace it further — flagging for
  the user's judgment call on whether this needs a raw-file fix or a segmentation-boundary fix.

No other raw-source data-quality issues found in this range — the rest of the anomalies I found
were extraction/rule-layer problems (wrong subject, wrong label, dropped clauses, etc.), not
problems with the source document itself.
