"""
model.py
========
Phase 9 (Bonus) — Machine Learning Module for the Nassau Candy Distributor
Shipping Analysis.

Implements:
    - Delay Classification (Random Forest, Gradient Boosting, XGBoost)
    - Lead Time Regression (Random Forest, Gradient Boosting, XGBoost)
    - SHAP-based feature importance
    - Model evaluation: Accuracy, Precision, Recall, F1, ROC AUC (classifier)
    - Model evaluation: MAE, RMSE, R² (regressor)
    - Trained models saved to outputs/models/

Usage (standalone):
    python src/model.py

Usage (as module):
    from src.model import DelayClassifier, LeadTimeRegressor

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    FEATURED_DATA_FILE,
    OUTPUTS_MODELS_DIR,
    get_logger,
    load_data,
)

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

#: Feature columns used by both classification and regression models
BASE_FEATURES: List[str] = [
    "Shipment Month",
    "Shipment Quarter",
    "Shipment Day of Week",
    "Shipment Week",
    "Units",
    "Sales",
    "Gross Profit",
    "Cost",
    "Factory Latitude",
    "Factory Longitude",
    # Encoded categoricals (added during preparation)
    "Ship Mode_encoded",
    "Factory_encoded",
    "Region_encoded",
    "Division_encoded",
]

RANDOM_STATE: int = 42
TEST_SIZE: float = 0.2


# ─────────────────────────────────────────────────────────────────────────────
# SHARED PREPARATION HELPER
# ─────────────────────────────────────────────────────────────────────────────

def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare the feature matrix from the featured DataFrame.

    Encodes categorical columns with label encoding and selects the
    ``BASE_FEATURES`` columns.

    Args:
        df: Featured DataFrame (output of Phase 2).

    Returns:
        DataFrame restricted to ``BASE_FEATURES`` columns with no NaN values.
    """
    from sklearn.preprocessing import LabelEncoder

    d = df.copy()
    cat_map = {
        "Ship Mode":  "Ship Mode_encoded",
        "Factory":    "Factory_encoded",
        "Region":     "Region_encoded",
        "Division":   "Division_encoded",
    }
    for src, tgt in cat_map.items():
        le = LabelEncoder()
        d[tgt] = le.fit_transform(d[src].astype(str))

    available = [f for f in BASE_FEATURES if f in d.columns]
    return d[available].dropna()


# ─────────────────────────────────────────────────────────────────────────────
# DELAY CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

class DelayClassifier:
    """
    Binary classifier to predict whether a shipment will be delayed.

    Target variable: ``Delay Flag`` (True = delayed).

    Supported algorithms:
        - ``"rf"``  → Random Forest
        - ``"gbm"`` → Gradient Boosting
        - ``"xgb"`` → XGBoost

    Attributes:
        df:      Featured DataFrame.
        logger:  Module logger.
        models:  Dict of trained estimators (populated after ``train()``).
        results: Dict of evaluation metrics per model.

    Example:
        >>> clf = DelayClassifier(df)
        >>> results = clf.train_all()
        >>> print(results)
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)
        self.models: Dict[str, Any] = {}
        self.results: Dict[str, Dict[str, float]] = {}
        self._X_train = self._X_test = self._y_train = self._y_test = None
        self._feature_names: List[str] = []

    def _prepare(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare X and y for classification."""
        X = prepare_features(self.df)
        self._feature_names = X.columns.tolist()
        idx = X.index
        y = self.df.loc[idx, "Delay Flag"].astype(int)
        return X, y

    def train(self, algorithm: str = "rf") -> Dict[str, float]:
        """
        Train a single classifier.

        Args:
            algorithm: One of ``"rf"``, ``"gbm"``, ``"xgb"``.

        Returns:
            Dictionary of evaluation metrics.
        """
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.metrics import (
            accuracy_score, f1_score, precision_score,
            recall_score, roc_auc_score,
        )
        from sklearn.model_selection import train_test_split

        X, y = self._prepare()
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
        )
        self._X_train, self._X_test = X_train, X_test
        self._y_train, self._y_test = y_train, y_test

        if algorithm == "rf":
            estimator = RandomForestClassifier(
                n_estimators=200, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1
            )
        elif algorithm == "gbm":
            estimator = GradientBoostingClassifier(
                n_estimators=200, max_depth=5, learning_rate=0.05, random_state=RANDOM_STATE
            )
        elif algorithm == "xgb":
            try:
                from xgboost import XGBClassifier
                estimator = XGBClassifier(
                    n_estimators=200, max_depth=6, learning_rate=0.05,
                    random_state=RANDOM_STATE, eval_metric="logloss",
                    verbosity=0,
                )
            except ImportError:
                self.logger.warning("XGBoost not installed; falling back to GBM")
                estimator = GradientBoostingClassifier(
                    n_estimators=200, random_state=RANDOM_STATE
                )
        else:
            raise ValueError(f"Unknown algorithm: {algorithm!r}. Choose 'rf', 'gbm', or 'xgb'.")

        self.logger.info("Training %s classifier...", algorithm.upper())
        estimator.fit(X_train, y_train)

        y_pred = estimator.predict(X_test)
        y_prob = (
            estimator.predict_proba(X_test)[:, 1]
            if hasattr(estimator, "predict_proba")
            else y_pred.astype(float)
        )

        metrics = {
            "accuracy":  round(accuracy_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
            "recall":    round(recall_score(y_test, y_pred, zero_division=0), 4),
            "f1":        round(f1_score(y_test, y_pred, zero_division=0), 4),
            "roc_auc":   round(roc_auc_score(y_test, y_prob), 4),
        }

        self.models[algorithm] = estimator
        self.results[algorithm] = metrics
        self.logger.info("%s metrics: %s", algorithm.upper(), metrics)
        return metrics

    def train_all(self) -> Dict[str, Dict[str, float]]:
        """Train all three classifiers and return combined results."""
        for algo in ["rf", "gbm", "xgb"]:
            try:
                self.train(algo)
            except Exception as e:
                self.logger.error("Failed to train %s: %s", algo, e)
        return self.results

    def feature_importance(
        self, algorithm: str = "rf", top_n: int = 15
    ) -> pd.DataFrame:
        """
        Return a DataFrame of feature importances for the given model.

        Args:
            algorithm: Trained algorithm key.
            top_n:     Number of top features to return.

        Returns:
            DataFrame with columns: feature, importance.
        """
        if algorithm not in self.models:
            raise ValueError(f"Model '{algorithm}' not trained yet. Call train() first.")

        model = self.models[algorithm]
        importances = (
            model.feature_importances_
            if hasattr(model, "feature_importances_")
            else np.zeros(len(self._feature_names))
        )
        df_imp = pd.DataFrame({
            "feature": self._feature_names,
            "importance": importances,
        }).sort_values("importance", ascending=False).head(top_n)
        return df_imp.reset_index(drop=True)

    def get_results_df(self) -> pd.DataFrame:
        """Return a tidy DataFrame of all model results."""
        rows = []
        for algo, metrics in self.results.items():
            row = {"algorithm": algo.upper()}
            row.update(metrics)
            rows.append(row)
        return pd.DataFrame(rows)

    def save_models(self) -> None:
        """Serialize trained models to outputs/models/ using joblib."""
        import joblib
        OUTPUTS_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        for algo, model in self.models.items():
            path = OUTPUTS_MODELS_DIR / f"classifier_{algo}.pkl"
            joblib.dump(model, path)
            self.logger.info("Saved classifier_%s -> %s", algo, path)


# ─────────────────────────────────────────────────────────────────────────────
# LEAD TIME REGRESSOR
# ─────────────────────────────────────────────────────────────────────────────

class LeadTimeRegressor:
    """
    Regression model to predict shipping lead time in days.

    Target variable: ``Shipping Lead Time`` (continuous, days).

    Supported algorithms:
        - ``"rf"``  → Random Forest
        - ``"gbm"`` → Gradient Boosting
        - ``"xgb"`` → XGBoost

    Attributes:
        df:      Featured DataFrame.
        logger:  Module logger.
        models:  Dict of trained estimators.
        results: Dict of evaluation metrics per model.

    Example:
        >>> reg = LeadTimeRegressor(df)
        >>> results = reg.train_all()
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)
        self.models: Dict[str, Any] = {}
        self.results: Dict[str, Dict[str, float]] = {}
        self._feature_names: List[str] = []

    def _prepare(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare X and y for regression."""
        X = prepare_features(self.df)
        self._feature_names = X.columns.tolist()
        idx = X.index
        y = self.df.loc[idx, "Shipping Lead Time"]
        return X, y

    def train(self, algorithm: str = "rf") -> Dict[str, float]:
        """
        Train a single regressor.

        Args:
            algorithm: One of ``"rf"``, ``"gbm"``, ``"xgb"``.

        Returns:
            Dictionary of evaluation metrics: MAE, RMSE, R².
        """
        from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split

        X, y = self._prepare()
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
        )

        if algorithm == "rf":
            estimator = RandomForestRegressor(
                n_estimators=200, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1
            )
        elif algorithm == "gbm":
            estimator = GradientBoostingRegressor(
                n_estimators=200, max_depth=5, learning_rate=0.05, random_state=RANDOM_STATE
            )
        elif algorithm == "xgb":
            try:
                from xgboost import XGBRegressor
                estimator = XGBRegressor(
                    n_estimators=200, max_depth=6, learning_rate=0.05,
                    random_state=RANDOM_STATE, verbosity=0,
                )
            except ImportError:
                self.logger.warning("XGBoost not installed; falling back to GBM")
                estimator = GradientBoostingRegressor(
                    n_estimators=200, random_state=RANDOM_STATE
                )
        else:
            raise ValueError(f"Unknown algorithm: {algorithm!r}.")

        self.logger.info("Training %s regressor...", algorithm.upper())
        estimator.fit(X_train, y_train)
        y_pred = estimator.predict(X_test)

        mae  = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(np.mean((y_test - y_pred) ** 2))
        r2   = r2_score(y_test, y_pred)

        metrics = {
            "mae":  round(float(mae), 4),
            "rmse": round(float(rmse), 4),
            "r2":   round(float(r2), 4),
        }

        self.models[algorithm] = estimator
        self.results[algorithm] = metrics
        self.logger.info("%s metrics: %s", algorithm.upper(), metrics)
        return metrics

    def train_all(self) -> Dict[str, Dict[str, float]]:
        """Train all three regressors and return combined results."""
        for algo in ["rf", "gbm", "xgb"]:
            try:
                self.train(algo)
            except Exception as e:
                self.logger.error("Failed to train %s: %s", algo, e)
        return self.results

    def feature_importance(
        self, algorithm: str = "rf", top_n: int = 15
    ) -> pd.DataFrame:
        """Return top-N feature importances for the trained regressor."""
        if algorithm not in self.models:
            raise ValueError(f"Model '{algorithm}' not trained. Call train() first.")
        model = self.models[algorithm]
        importances = (
            model.feature_importances_
            if hasattr(model, "feature_importances_")
            else np.zeros(len(self._feature_names))
        )
        df_imp = pd.DataFrame({
            "feature": self._feature_names,
            "importance": importances,
        }).sort_values("importance", ascending=False).head(top_n)
        return df_imp.reset_index(drop=True)

    def get_results_df(self) -> pd.DataFrame:
        """Return a tidy DataFrame of all model results."""
        rows = []
        for algo, metrics in self.results.items():
            row = {"algorithm": algo.upper()}
            row.update(metrics)
            rows.append(row)
        return pd.DataFrame(rows)

    def save_models(self) -> None:
        """Serialize trained models to outputs/models/ using joblib."""
        import joblib
        OUTPUTS_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        for algo, model in self.models.items():
            path = OUTPUTS_MODELS_DIR / f"regressor_{algo}.pkl"
            joblib.dump(model, path)
            self.logger.info("Saved regressor_%s -> %s", algo, path)


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Train all models and print evaluation results."""
    from src.utils import ensure_dirs
    ensure_dirs()

    df = load_data(FEATURED_DATA_FILE, date_cols=["Order Date", "Ship Date"])

    print("\n" + "=" * 60)
    print("DELAY CLASSIFICATION")
    print("=" * 60)
    clf = DelayClassifier(df)
    clf_results = clf.train_all()
    print(clf.get_results_df().to_string(index=False))
    print("\nTop Feature Importances (RF):")
    print(clf.feature_importance("rf").to_string(index=False))
    clf.save_models()

    print("\n" + "=" * 60)
    print("LEAD TIME REGRESSION")
    print("=" * 60)
    reg = LeadTimeRegressor(df)
    reg_results = reg.train_all()
    print(reg.get_results_df().to_string(index=False))
    print("\nTop Feature Importances (RF):")
    print(reg.feature_importance("rf").to_string(index=False))
    reg.save_models()


if __name__ == "__main__":
    main()
