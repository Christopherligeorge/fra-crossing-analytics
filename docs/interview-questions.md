# Explain it before claiming independent mastery

## 1. Git safety
- How do working files, staged files, commits and pushed history differ?
- Why does adding a leaked credential to gitignore not undo the leak?
- Why is a file-size check separate from ignore rules?

## 2. Sources and staging
- What should staging normalize, and what must remain raw here?
- Why are source IDs unique within a dataset rather than across both inventories?
- Why do frozen URLs alone not prove a reproducible vintage?

## 3. Intermediate models
- Why is the revision period open on the left and closed on the right?
- What goes wrong if closed/conflicting revisions are removed before selecting latest?
- Why can history not be calculated over eligible panel rows alone?

## 4. Marts
- What exactly is the fact-table grain, and how can a join break it?
- Why are state and warning devices on the fact rather than the identity dimension?
- Why does the dimension include crossings that never enter the panel?

## 5. Tests
- Which wrong implementation could pass a row-count test?
- How do hand-computed edge cases complement full reference parity?
- What proves that outcome-year reports do not enter history?

## 6. Documentation
- Which pieces of lineage does dbt infer from ref/source calls?
- How does a good column description differ from restating its name?
- Why must historical revision dates not be described as public-availability dates?

## 7. CI
- What does the small fixture prove, and what can it not prove?
- Why must tests work on a fresh clone without your local profile?
- What should happen when an upstream key becomes duplicated?

## 8. Python evaluation
- Why keep training/calibration/selection/test separate?
- Why compare predictions and columns instead of rounded AP alone?
- Why are the 2024–2025 years no longer untouched holdouts?

## 9. Dashboard
- What are the numerator and denominator of top-decile capture?
- How does within-state ranking differ from national allocation?
- How do you distinguish synthetic CI data from genuine result summaries?

## 10. Portfolio presentation
- Which decisions and code can you currently explain without assistance?
- What did AI implement, and what have you independently reproduced?
- Which conclusion would this project not support even if all engineering tests pass?
