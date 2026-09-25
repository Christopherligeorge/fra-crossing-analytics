# Preserved legacy behavior, not a recommended date parser

Full-column parity initially found 1,158 crossing-years with differences in gate
counts, signs/signals and the future-warning flag. The cause was the original
`pandas.to_datetime(..., format='mixed')` interpretation of compact installation dates.
For example, `071975` is parsed as **2075-07-19**, not July 1975. `052024` is parsed as
2024-05-20. The two-digit-year century pivot also depends on the parser's current year.

This project reproduces the 2026 reference behavior explicitly in
`legacy_measurement_date`: six digits use MMDDYY with a fixed 76 pivot. Four-digit
years, ISO timestamps and the observed textual date formats are handled separately.
The macro is a compatibility rule for this frozen dataset, not a general FRA-date
normalizer. New vintages need their own format audit; unsupported formats become null.

The rebuild does **not** silently reinterpret source fields, change masks or rerun a
corrected scientific study. Exact parity is evidence of reproduction, not proof that
the original interpretation is substantively right. A future correction must inspect
the FRA field definition, establish a defensible parsing policy, version the research
panel, rerun evaluation and report any changes separately. No such correction or new
finding is claimed here.
