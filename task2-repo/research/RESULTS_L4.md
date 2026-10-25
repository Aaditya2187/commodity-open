# L4: news sentiment as a learning-only feature (26 Oct 2026, ~01:20 IST)

Ran `python research/l4_news.py` (PYTHONPATH=research) on this machine after setup.
`research/news_holdout.parquet` was already present from `news_feats.py` (PointInTime reads of
`pack/news/news_rows`). Output also in `research/sweep_L4.txt`.

## Univariate (holdout keys with day news)

| Window | Feature | n | news-dir % | Disagree with gap: news right | gap right |
|---|---|---|---|---|---|
| 16 Jul–31 Aug | news_night | 635 | 43.0 | 29.3 | 47.8 |
| 16 Jul–31 Aug | news_day | 640 | 45.3 | 33.1 | 45.1 |
| Sep–Oct | news_night | 750 | 30.9 | 22.5 | 50.1 |
| Sep–Oct | news_day | 760 | 29.7 | 20.5 | 51.9 |

The lexicon score is anti-predictive relative to the gap: when they disagree, the gap wins.

## Learner replay (HO only; news is 0 before June so the frozen fit cannot use it)

| Config | aux | D | gain | S | gates |
|---|---|---|---|---|---|
| L3 cat every=5 (no news) | coreh:1,2,3,4 | 72.0 | +0.96 | 60.6 | YYYY. |
| L4 = L3 + news | coreh:1,2,3,4 | 72.0 | +0.96 | 60.6 | YYYY. |
| L4 logit + news | coreh:1,2,3,4 | 71.3 | −0.72 | 57.1 | YY.Y. |
| L3 cat every=5 (no news) | noncore:5 | 59.9 | −0.48 | 53.3 | .Y... |
| L4 = L3 + news | noncore:5 | 60.1 | −0.24 | 53.4 | YY... |
| L4 logit + news | noncore:5 | 61.1 | −1.44 | 53.7 | YY... |

## Verdict

**FAILED.** News features do not raise the paired gain on the holdout; logit+news loses. Do not ship.
Previous Windows OOM on L4 was environmental; the experiment itself completes in ~20 s here.
