# Historical decision analysis v1.0

## Purpose

The goal is not to find one blogger to copy. It is to extract transferable decision rules:

- how the author recognizes regimes and opportunities;
- how they enter, size, reduce, exit, and admit error;
- what changes between drawdowns, rallies, volatility spikes, and calm markets;
- whether public claims are timely, falsifiable, and consistent with visible execution evidence;
- which behavior is useful to the reader and under what limits.

Use a capability matrix and role map. Do not compress everything into a single leaderboard.

## Three-layer model

### Claim

One time-stamped, symbol-specific, direction-specific statement. Freeze it without seeing future outcomes.

Minimum fields:

- `claim_id`, `feed_id`, `author_uid`, `published_at`;
- evidence quote and source path;
- symbol, direction, action, horizon;
- conditions, invalidation, sizing/risk/exit language;
- evidence level `A/B/C/D`;
- confidence and ambiguity.

### Episode

An episode links claims about the same thesis through time. It captures initiation, reinforcement, update, reversal, execution, and closure.

Suggested update labels:

- `evidence_driven`
- `price_driven`
- `position_reinforcement`
- `disciplined_execution`
- `thesis_unchanged_with_new_evidence`
- `reversal`
- `no_observed_update`
- `insufficient_evidence`

Absence of a public update is not proof that the author took no action.

### Profile

Aggregate only after claim and episode review. Profile dimensions include:

- source of edge;
- preferred horizon and instruments;
- entry logic;
- sizing and concentration;
- loss control;
- profit management;
- thesis-update discipline;
- communication quality and accountability;
- regime dependence;
- evidence coverage.

## Evidence levels

- `A`: image or primary record showing an order, fill, cost, position, or P&L, actually inspected and attributable.
- `B`: explicit first-person trade action in text.
- `C`: directional opinion, valuation view, forecast, or thesis without verified action.
- `D`: mention, repost, joke, question, or attention signal.

`C` and `D` never establish a holding. `A` establishes only what is visible in the cited record, not the whole account.

Run opinion and execution analysis as separate tracks:

- opinion track: `C` and above;
- execution/discipline track: only `A/B`;
- tone/attention track: `D` may be included with clear labels.

## No-time-travel protocol

1. Freeze claim fields using only the post and information already public by its timestamp.
2. Context uses the last fully completed bar known at that time.
3. Forward evaluation begins at the first tradable open after publication.
4. Only after claims are frozen may the analyst reveal 1/5/20/60-session paths.
5. Any retrospective interpretation must be labeled as such.

Daily data cannot validate intraday execution prices. Option outcomes require contract, side, strike, expiry, timestamp, and action; otherwise evaluate only the underlying directional path.

## Market context

At minimum record:

- market and sector benchmarks;
- close relative to 20- and 60-session averages;
- 20-session moving-average slope;
- rolling realized volatility and percentile;
- drawdown from a recent high;
- gap or extreme daily move;
- event context when verifiable from a contemporaneous source.

A simple regime grid may combine:

- trend: up / down / mixed;
- volatility: low / normal / high;
- event: ordinary / extreme.

Do not overfit regime labels to the future outcome.

## Outcome measures

For each eligible directional claim:

- 1/5/20/60-session return from next tradable open;
- benchmark-relative return;
- maximum favorable excursion (MFE);
- maximum adverse excursion (MAE);
- direction hit;
- missing-data and delisting flags.

Outcome is not account return. A correct direction is not proof of profitable execution.

## Strategy completeness

Score each dimension independently as `0/1/2`; do not sum into a universal total:

- thesis clarity;
- evidence density;
- falsifiability;
- entry rule;
- sizing rule;
- risk/invalidation rule;
- exit/profit-management rule.

Explain each score with citations and at least one counterexample.

## Tone

Tone is not character diagnosis. Code observable language only:

- valence: `-2..2`;
- arousal, certainty, urgency, conditionality, risk awareness, evidence density, accountability: `0..4`.

Compare tone changes with contemporaneous market state and the author's prior claims. Do not infer private emotions, holdings, or mental-health conditions.

## Minimum evidence and uncertainty

- fewer than 20 eligible claims per author/window: descriptive only;
- 20 or more: report bootstrap 80% and 95% intervals where useful;
- multiple tests: Benjamini-Hochberg false discovery rate at 10%;
- temporal stability: use a 70/30 chronological split when at least 10 eligible claims exist in both practical segments;
- qualitative confidence:
  - high: at least 8 episodes, at least 2 regimes, at least 70% pattern consistency, and counterexample review;
  - medium: 4–7 episodes;
  - exploratory: 2–3 episodes;
  - one episode: case only.

For a manually coded study, double-code at least 10% of eligible episodes and at least 30 episodes when available. Target Cohen's kappa of 0.70 or above. If reliability fails, stop public comparative conclusions and revise the codebook.

## Final deliverables

For each author:

1. one direct, bounded conclusion;
2. what the author is genuinely useful for;
3. trading style and strategy mechanics;
4. behavior across regimes;
5. execution evidence coverage;
6. strongest counterexample;
7. confidence and missingness;
8. rules the reader can adopt;
9. behaviors the reader should not copy.

Across authors, assign complementary roles—such as idea generation, valuation, trend/risk control, or execution diary—only when supported. Do not imply that agreement among public bloggers is independent confirmation.
