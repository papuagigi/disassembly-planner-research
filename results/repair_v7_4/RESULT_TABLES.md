# v7.4 result tables (offline/aggregate74.py; all 180 frozen episodes, unfiltered)

| condition | success | Wilson 95% | wasted checks, successful (median [IQR], max) | zero-waste | tokens median | calls median | elapsed s median (model / other) |
|---|---|---|---|---|---|---|---|
| a1/A/none | 36/36 | [0.904, 1.0] | 10 [1.75–20.5], max 61 | 8/36 | 19292 | 1 | 30.15 (10.65 / 17.9) |
| a1/B/S5 | 36/36 | [0.904, 1.0] | 6 [4.5–9.75], max 18 | 6/36 | 41384 | 2 | 35.45 (18.6 / 17.65) |
| a1/C/S5 | 36/36 | [0.904, 1.0] | 8 [3–14], max 48 | 5/36 | 62966.5 | 3 | 40.1 (21.7 / 16.7) |
| a2/B/S5+note | 36/36 | [0.904, 1.0] | 0 [0–0], max 6 | 35/36 | 43102.5 | 2 | 31.9 (20.2 / 10.8) |
| a2/C/S5+note | 36/36 | [0.904, 1.0] | 0 [0–0], max 0 | 36/36 | 41112 | 2 | 24.3 (13.85 / 11.1) |

## By part-count tier (mean wasted checks of successful episodes; success)

| tier | a1/A/none | a1/B/S5 | a1/C/S5 | a2/B/S5+note | a2/C/S5+note |
|---|---|---|---|---|---|
| 5 parts | 12.42 (12/12) | 7.75 (12/12) | 4.5 (12/12) | 0 (12/12) | 0 (12/12) |
| 6 parts | 8.67 (12/12) | 4.25 (12/12) | 8.67 (12/12) | 0.5 (12/12) | 0 (12/12) |
| 7 parts | 19.83 (12/12) | 10 (12/12) | 21.83 (12/12) | 0 (12/12) | 0 (12/12) |

## Per CAD (wasted checks of the 3 repeats: median, max; success)

| CAD | tier | a1/A/none | a1/B/S5 | a1/C/S5 | a2/B/S5+note | a2/C/S5+note |
|---|---|---|---|---|---|---|
| asap_04098 | 5 | 7, 14 (3/3) | 6, 6 (3/3) | 6, 7 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_07711 | 5 | 13, 20 (3/3) | 7, 7 (3/3) | 2, 7 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_07714 | 5 | 12, 23 (3/3) | 18, 18 (3/3) | 8, 19 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_08203 | 5 | 0, 40 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_03391 | 6 | 20, 22 (3/3) | 8, 8 (3/3) | 13, 17 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_04714 | 6 | 12, 12 (3/3) | 6, 6 (3/3) | 12, 12 (3/3) | 0, 6 (3/3) | 0, 0 (3/3) |
| asap_06262 | 6 | 0, 1 (3/3) | 3, 3 (3/3) | 9, 10 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_06414 | 6 | 5, 16 (3/3) | 0, 0 (3/3) | 5, 8 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_00650 | 7 | 34, 37 (3/3) | 15, 15 (3/3) | 20, 30 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_01680 | 7 | 26, 61 (3/3) | 5, 5 (3/3) | 22, 36 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_02874 | 7 | 0, 0 (3/3) | 5, 5 (3/3) | 6, 7 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |
| asap_08183 | 7 | 10, 29 (3/3) | 15, 15 (3/3) | 42, 48 (3/3) | 0, 0 (3/3) | 0, 0 (3/3) |

## Paired per-CAD comparisons (descriptive; Wilcoxon on per-CAD means is secondary)

| x → y | metric | CADs y lower | y higher | ties | median diff (y−x) | Wilcoxon p |
|---|---|---|---|---|---|---|
| a1/A/none → a1/B/S5 | wasted_checks | 8 | 4 | 0 | -4.83333 | 0.0522 |
| a1/A/none → a1/B/S5 | total_tokens | 0 | 12 | 0 | 21853.2 | 0.0005 |
| a1/A/none → a1/B/S5 | elapsed_seconds | 5 | 7 | 0 | 0.466667 | 0.791 |
| a1/B/S5 → a1/C/S5 | wasted_checks | 4 | 7 | 1 | 4.16667 | 0.1152 |
| a1/B/S5 → a1/C/S5 | total_tokens | 1 | 11 | 0 | 30111.5 | 0.001 |
| a1/B/S5 → a1/C/S5 | elapsed_seconds | 6 | 6 | 0 | 2.25 | 0.9097 |
| a1/B/S5 → a2/B/S5+note | wasted_checks | 10 | 0 | 2 | -5.5 | 0.002 |
| a1/B/S5 → a2/B/S5+note | total_tokens | 1 | 11 | 0 | 1930.33 | 0.0093 |
| a1/B/S5 → a2/B/S5+note | elapsed_seconds | 5 | 7 | 0 | 0.666667 | 0.5693 |
| a1/C/S5 → a2/C/S5+note | wasted_checks | 11 | 0 | 1 | -8.33333 | 0.001 |
| a1/C/S5 → a2/C/S5+note | total_tokens | 11 | 1 | 0 | -30385.8 | 0.001 |
| a1/C/S5 → a2/C/S5+note | elapsed_seconds | 11 | 1 | 0 | -14.6 | 0.0015 |

Note writer: 12 notes, problems none, tokens per note 14643–16074.

Invalid (excluded) episodes: none
