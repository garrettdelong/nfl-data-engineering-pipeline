"""Train baseline models for NFL play success prediction."""

import json

import joblib
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
    FEATURE_COLUMNS,
    INPUT_CSV_PATH,
    METRICS_PATH,
    MODEL_PATH,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)

RANDOM_STATE = 42


def load_dataset():
    """Load the CSV and verify its required columns."""
    if not INPUT_CSV_PATH.exists():
        raise FileNotFoundError(
            "ML feature CSV not found. Export the dbt model to:\n"
            f"{INPUT_CSV_PATH}"
        )

    data = pd.read_csv(INPUT_CSV_PATH)
    data.columns = [column.strip().lower() for column in data.columns]

    required_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN])
    missing_columns = sorted(required_columns - set(data.columns))

    if missing_columns:
        raise ValueError(
            "Input CSV is missing expected columns: "
            + ", ".join(missing_columns)
        )

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
        positive_class_index = list(model.classes_).index(1)
        positive_probabilities = class_probabilities[
            :, positive_class_index
        ]

        metrics["roc_auc"] = float(
            roc_auc_score(target, positive_probabilities)
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


def save_artifacts(logistic_model, metrics):
    """Save the metrics and complete fitted pipeline."""
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with METRICS_PATH.open("w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, indent=2)

    joblib.dump(logistic_model, MODEL_PATH)

    print(f"\nmetrics saved to: {METRICS_PATH}")
    print(f"model saved to: {MODEL_PATH}")


def main():
    data = load_dataset()

    train_seasons, validation_season, test_season = select_seasons(data)

    print(f"train seasons: {train_seasons}")
    print(f"validation season: {validation_season}")
    print(f"test season: {test_season}")

    (
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
        f"train={len(x_train)} "
        f"validation={len(x_validation)} "
        f"test={len(x_test)}"
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

    metrics = {
        "seasons": {
            "train": train_seasons,
            "validation": validation_season,
            "test": test_season,
        },
        "row_counts": {
            "train": len(x_train),
            "validation": len(x_validation),
            "test": len(x_test),
        },
        "dummy_validation": dummy_validation_metrics,
        "logistic_validation": logistic_validation_metrics,
        "logistic_test": logistic_test_metrics,
    }

    save_artifacts(logistic_model, metrics)


if __name__ == "__main__":
    main()
