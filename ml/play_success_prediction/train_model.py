"""Train baseline models for NFL play success prediction."""

import sys
import uuid

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import (
    CATEGORICAL_FEATURES,
    FEATURE_DATABASE,
    FEATURE_COLUMNS,
    FEATURE_SCHEMA,
    FEATURE_TABLE,
    ID_COLUMNS,
    METRICS_TABLE,
    NUMERIC_FEATURES,
    PREDICTIONS_TABLE,
    REPO_ROOT,
    RESULT_DATABASE,
    RESULT_SCHEMA,
    TARGET_COLUMN,
)

sys.path.insert(0, str(REPO_ROOT))

from data.snowflake_client import (  # noqa: E402
    connect_snowflake,
    get_snowflake_config_from_env,
    read_table_to_dataframe,
    write_dataframe_to_table,
)

RANDOM_STATE = 42


def load_dataset(connection, config):
    """Load the feature table from Snowflake and validate columns."""
    columns = ID_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]

    data = read_table_to_dataframe(
        connection=connection,
        table_name=FEATURE_TABLE,
        columns=columns,
        database=FEATURE_DATABASE,
        schema=FEATURE_SCHEMA,
    )

    required_columns = set(columns)
    missing_columns = sorted(required_columns - set(data.columns))

    if missing_columns:
        raise ValueError(
            "Snowflake feature table is missing expected columns: "
            + ", ".join(missing_columns)
        )

    if data.empty:
        raise ValueError("Snowflake feature table returned zero rows.")

    for column in NUMERIC_FEATURES + [TARGET_COLUMN]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    return data


def select_seasons(data):
    """Select chronological training, validation, and test seasons."""
    seasons = sorted(data["season"].dropna().unique().tolist())

    if len(seasons) < 3:
        raise ValueError(
            "At least three seasons are required for chronological splitting."
        )

    train_seasons = seasons[:-2]
    validation_season = seasons[-2]
    test_season = seasons[-1]

    return train_seasons, validation_season, test_season


def split_dataset(
    data,
    train_seasons,
    validation_season,
    test_season,
):
    """Create feature and target datasets for each time period."""
    train_data = data[data["season"].isin(train_seasons)]
    validation_data = data[data["season"] == validation_season]
    test_data = data[data["season"] == test_season]

    splits = {
        "train": train_data,
        "validation": validation_data,
        "test": test_data,
    }

    empty_splits = [
        name for name, split_data in splits.items() if split_data.empty
    ]

    if empty_splits:
        raise ValueError(
            "Chronological split produced empty datasets: "
            + ", ".join(empty_splits)
        )

    x_train = train_data[FEATURE_COLUMNS]
    y_train = train_data[TARGET_COLUMN]

    x_validation = validation_data[FEATURE_COLUMNS]
    y_validation = validation_data[TARGET_COLUMN]

    x_test = test_data[FEATURE_COLUMNS]
    y_test = test_data[TARGET_COLUMN]

    return (
        train_data,
        validation_data,
        test_data,
        x_train,
        y_train,
        x_validation,
        y_validation,
        x_test,
        y_test,
    )


def build_logistic_pipeline():
    """Build preprocessing and logistic regression as one pipeline."""
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "one_hot_encoder",
                OneHotEncoder(handle_unknown="ignore"),
            ),
        ]
    )

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                categorical_pipeline,
                CATEGORICAL_FEATURES,
            ),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def positive_class_index(model):
    """Find the probability column for class 1."""
    if hasattr(model, "classes_"):
        classes = model.classes_
    else:
        classes = model.named_steps["classifier"].classes_

    return list(classes).index(1)


def evaluate_model(model, features, target):
    """Calculate classification metrics for one fitted model."""
    predictions = model.predict(features)

    metrics = {
        "accuracy": float(accuracy_score(target, predictions)),
        "precision": float(
            precision_score(target, predictions, zero_division=0)
        ),
        "recall": float(
            recall_score(target, predictions, zero_division=0)
        ),
        "f1": float(f1_score(target, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(
            target,
            predictions,
            labels=[0, 1],
        ).tolist(),
        "roc_auc": None,
    }

    if hasattr(model, "predict_proba") and target.nunique() == 2:
        class_probabilities = model.predict_proba(features)
        success_probabilities = class_probabilities[
            :,
            positive_class_index(model),
        ]

        metrics["roc_auc"] = float(
            roc_auc_score(target, success_probabilities)
        )

    return metrics


def print_metrics(model_name, split_name, metrics):
    """Print one evaluation result in a readable format."""
    print(f"\n{model_name} - {split_name}")
    print(f"accuracy: {metrics['accuracy']:.4f}")
    print(f"precision: {metrics['precision']:.4f}")
    print(f"recall: {metrics['recall']:.4f}")
    print(f"f1: {metrics['f1']:.4f}")

    if metrics["roc_auc"] is None:
        print("roc_auc: unavailable")
    else:
        print(f"roc_auc: {metrics['roc_auc']:.4f}")

    print(f"confusion_matrix: {metrics['confusion_matrix']}")


def build_metric_rows(run_id, model_name, split_name, metrics):
    """Convert metrics into a Snowflake-ready DataFrame."""
    rows = []

    for metric_name, metric_value in metrics.items():
        if metric_name == "confusion_matrix":
            rows.append(
                {
                    "run_id": run_id,
                    "model_name": model_name,
                    "split_name": split_name,
                    "metric_name": metric_name,
                    "metric_value": None,
                    "metric_text": str(metric_value),
                }
            )
        else:
            rows.append(
                {
                    "run_id": run_id,
                    "model_name": model_name,
                    "split_name": split_name,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "metric_text": None,
                }
            )

    return rows


def build_prediction_frame(
    run_id,
    model,
    test_data,
    x_test,
    y_test,
):
    """Build row-level test predictions for Snowflake."""
    predictions = model.predict(x_test)
    class_probabilities = model.predict_proba(x_test)
    success_probabilities = class_probabilities[
        :,
        positive_class_index(model),
    ]

    prediction_frame = test_data[ID_COLUMNS + ["season"]].copy()
    prediction_frame["run_id"] = run_id
    prediction_frame["model_name"] = "logistic_regression"
    prediction_frame["split_name"] = "test"
    prediction_frame["actual_is_successful_play"] = y_test.to_numpy()
    prediction_frame["predicted_is_successful_play"] = predictions
    prediction_frame["predicted_success_probability"] = success_probabilities

    return prediction_frame[
        [
            "run_id",
            "model_name",
            "split_name",
            "game_id",
            "play_id",
            "season",
            "actual_is_successful_play",
            "predicted_is_successful_play",
            "predicted_success_probability",
        ]
    ]


def set_created_at_for_run(connection, run_id):
    """Set created_at in Snowflake to avoid pandas timestamp encoding issues."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
UPDATE {RESULT_DATABASE}.{RESULT_SCHEMA}.{METRICS_TABLE}
SET created_at = CURRENT_TIMESTAMP()
WHERE run_id = %s
    AND created_at IS NULL
""".strip(),
            (run_id,),
        )
        cursor.execute(
            f"""
UPDATE {RESULT_DATABASE}.{RESULT_SCHEMA}.{PREDICTIONS_TABLE}
SET created_at = CURRENT_TIMESTAMP()
WHERE run_id = %s
    AND created_at IS NULL
""".strip(),
            (run_id,),
        )


def write_results(
    connection,
    run_id,
    metric_frame,
    prediction_frame,
):
    """Write metrics and predictions to existing Snowflake tables."""
    write_dataframe_to_table(
        connection=connection,
        dataframe=metric_frame,
        table_name=METRICS_TABLE,
        database=RESULT_DATABASE,
        schema=RESULT_SCHEMA,
    )
    write_dataframe_to_table(
        connection=connection,
        dataframe=prediction_frame,
        table_name=PREDICTIONS_TABLE,
        database=RESULT_DATABASE,
        schema=RESULT_SCHEMA,
    )
    set_created_at_for_run(connection, run_id)

    print(
        "\nmetrics written to Snowflake table: "
        f"{RESULT_DATABASE}.{RESULT_SCHEMA}.{METRICS_TABLE}"
    )
    print(
        "predictions written to Snowflake table: "
        f"{RESULT_DATABASE}.{RESULT_SCHEMA}.{PREDICTIONS_TABLE}"
    )


def main():
    config = get_snowflake_config_from_env()
    run_id = str(uuid.uuid4())

    connection = connect_snowflake(config)

    try:
        data = load_dataset(connection, config)

        train_seasons, validation_season, test_season = select_seasons(data)

        print(f"train seasons: {train_seasons}")
        print(f"validation season: {validation_season}")
        print(f"test season: {test_season}")

        (
            train_data,
            validation_data,
            test_data,
            x_train,
            y_train,
            x_validation,
            y_validation,
            x_test,
            y_test,
        ) = split_dataset(
            data,
            train_seasons,
            validation_season,
            test_season,
        )

        print(
            "split rows: "
            f"train={len(train_data)} "
            f"validation={len(validation_data)} "
            f"test={len(test_data)}"
        )

        dummy_model = DummyClassifier(strategy="most_frequent")
        dummy_model.fit(x_train, y_train)

        logistic_model = build_logistic_pipeline()
        logistic_model.fit(x_train, y_train)

        dummy_validation_metrics = evaluate_model(
            dummy_model,
            x_validation,
            y_validation,
        )
        logistic_validation_metrics = evaluate_model(
            logistic_model,
            x_validation,
            y_validation,
        )
        logistic_test_metrics = evaluate_model(
            logistic_model,
            x_test,
            y_test,
        )

        print_metrics(
            "DummyClassifier",
            "validation",
            dummy_validation_metrics,
        )
        print_metrics(
            "LogisticRegression",
            "validation",
            logistic_validation_metrics,
        )
        print_metrics(
            "LogisticRegression",
            "test",
            logistic_test_metrics,
        )

        metric_rows = []
        metric_rows.extend(
            build_metric_rows(
                run_id,
                "dummy_classifier",
                "validation",
                dummy_validation_metrics,
            )
        )
        metric_rows.extend(
            build_metric_rows(
                run_id,
                "logistic_regression",
                "validation",
                logistic_validation_metrics,
            )
        )
        metric_rows.extend(
            build_metric_rows(
                run_id,
                "logistic_regression",
                "test",
                logistic_test_metrics,
            )
        )

        metric_frame = pd.DataFrame(metric_rows)
        prediction_frame = build_prediction_frame(
            run_id,
            logistic_model,
            test_data,
            x_test,
            y_test,
        )

        write_results(
            connection,
            run_id,
            metric_frame,
            prediction_frame,
        )

        print(f"run_id: {run_id}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
