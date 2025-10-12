# Benchmark Report

This report summarises accuracy and performance across implementations and algorithms, aggregated over all seeds found in Results/Bench.

## Summary (all seeds)

| implementation   | algorithm   | scope   |   queries |   accuracy_at_1 |   median_wall_ms |   p90_wall_ms |   median_rank_ms |   p90_rank_ms |
|:-----------------|:------------|:--------|----------:|----------------:|-----------------:|--------------:|-----------------:|--------------:|
| python           | keyword     | topic   |       165 |        0.890909 |           0.142  |        0.6986 |           0.1385 |        0.6938 |
| python           | tfidf       | topic   |       165 |        0.890909 |           0.1215 |        0.5206 |           0.1195 |        0.5186 |
| rust             | keyword     | topic   |       165 |        0.981818 |           0.488  |        1.8398 |           0.488  |        1.8398 |
| rust             | tfidf       | topic   |       165 |        0.981818 |           1.249  |        3.8354 |           1.249  |        3.8354 |

## Speedup Ratios (median wall_ms)

speedup = median_wall_ms(baseline) / median_wall_ms(contender) — larger means the contender is faster.

| algorithm   | scope   | baseline   | contender   |    speedup |
|:------------|:--------|:-----------|:------------|-----------:|
| keyword     | topic   | python     | rust        |  0.290984  |
| keyword     | topic   | rust       | python      |  3.43662   |
| tfidf       | topic   | python     | rust        |  0.0972778 |
| tfidf       | topic   | rust       | python      | 10.2798    |

## Figures — topic scope

![accuracy_bar topic](Results/Bench/Plots/accuracy_bar_topic.png)

![wall_ms_box topic](Results/Bench/Plots/wall_ms_box_topic.png)

![stage_ms_stacked topic](Results/Bench/Plots/stage_ms_stacked_topic.png)

![scalability topic](Results/Bench/Plots/scalability_wall_vs_decksize_topic.png)

![wall_ms_hist topic](Results/Bench/Plots/wall_ms_hist_topic.png)


## Errors

| implementation   | algorithm   | scope   | deck_name                                                                                    | query_id   | error             |
|:-----------------|:------------|:--------|:---------------------------------------------------------------------------------------------|:-----------|:------------------|
| python           | keyword     | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | fog:L)nj-Y | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | i(c$F-gDVE | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | j>O_%hXJ6T | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | tl^/vySVPX | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | HLzdZ8|],- | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | Ko!kctM>pa | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | N1(ly!o6~[ | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | QIBV4j$uR_ | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | uP3$;!azU| | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | A^*Q]]cnrW | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | H`^v,bBQ?, | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | JGbo@t7Dg= | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | QmN}R>/q,4 | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | g1JaxSzab< | Non-zero exit (1) |
| python           | keyword     | topic   | Launch into Computing::Unit 06 - Principles of Artificial Intelligence (AI)                  | wmtyrU@<(} | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | fog:L)nj-Y | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | i(c$F-gDVE | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | j>O_%hXJ6T | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 01 - What is Computing?                                          | tl^/vySVPX | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | HLzdZ8|],- | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | Ko!kctM>pa | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | N1(ly!o6~[ | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | QIBV4j$uR_ | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 02 - Logical Foundations: Boolean Algebra, Gates, and Set Theory | uP3$;!azU| | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | A^*Q]]cnrW | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | H`^v,bBQ?, | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | JGbo@t7Dg= | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | QmN}R>/q,4 | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 05 - Data Science and Storage                                    | g1JaxSzab< | Non-zero exit (1) |
| python           | tfidf       | topic   | Launch into Computing::Unit 06 - Principles of Artificial Intelligence (AI)                  | wmtyrU@<(} | Non-zero exit (1) |
