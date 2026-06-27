# Play Success Prediction

This module extends the NFL data engineering pipeline with a small,
explainable machine learning project. The objective is to predict whether an
offensive play will be successful using only information available before the
snap.

## Current Status

The dbt feature table is implemented and tested:

`data/nfl_data/models/marts/ml/ml_play_success_features.sql`

The Python module is currently a scaffold. Model training, evaluation, and
artifact generation have not been implemented yet.

## Feature Table

The dbt model has one row per `game_id + play_id` and is built from:

- `fct_play` for modeled play identifiers and core fields
- `stg_play_by_play` for additional pre-snap context and eligibility filters
- `dim_game` for roof, surface, temperature, and wind

Eligible plays:

- First through fourth down
- Pass or run play types
- Non-null yards to go, yard line, yards gained, and drive
- Not a two-point attempt
- Not a quarterback kneel or spike
- Not an accepted penalty play
- Not an aborted play

Sacks and scrambles are not directly excluded. They remain eligible when the
source represents them as pass or run plays.

## Target

The numeric target is `is_successful_play`:

- `1` for a touchdown
- `1` on first down when yards gained is at least 40% of yards to go
- `1` on second down when yards gained is at least 60% of yards to go
- `1` on third or fourth down when yards gained is at least yards to go
- `0` otherwise

## Leakage Controls

The final feature table excludes fields that describe or derive from the play
result. `yards_gained` and `touchdown` are used only to create the target.
`play_type` is used only to filter eligible plays.

The final table does not include:

- `play_type`
- `yards_gained`
- `touchdown`
- `success`
- `epa`
- sacks, completions, interceptions, or first-down results
- pass, rush, or scramble result indicators
- play description
- post-play score fields

## Planned Baseline

The first training implementation should:

1. Read `ml_play_success_features` from Snowflake.
2. Split training and test data chronologically by season.
3. Train a dummy classifier and logistic regression baseline.
4. Evaluate accuracy, precision, recall, F1, ROC-AUC, and a confusion matrix.
5. Save the trained model under `models/`.
6. Save metrics and predictions under `outputs/`.

## Structure

```text
ml/play_success_prediction/
|-- README.md
|-- config.py
|-- train_model.py
|-- requirements.txt
|-- models/
`-- outputs/
```

Generated model artifacts and output files should not be committed unless they
are intentionally selected as small portfolio examples.
