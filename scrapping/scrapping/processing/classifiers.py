"""
scrapping.processing.classifiers

Lightweight classification hooks for QA and enrichment.

Use cases:
- classify "is_job_post" vs "noise"
- tag content categories (e.g., product, news, legal doc)
- detect page types (login wall, anti-bot, empty)

V1 includes:
- BaseClassifier interface
- KeywordClassifier baseline (fast, explainable)
- Optional SklearnTextClassifier wrapper (if joblib/sklearn installed)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from scrapping.extraction.transforms import normalize_ws


@dataclass
class Classification:
    label: str
    score: float  # 0..1
    meta: Dict[str, Any] = None


class BaseClassifier(Protocol):
    name: str

    def predict(self, item: Dict[str, Any]) -> Classification:
        ...


# ---------------------------------------------------------------------
# Keyword baseline (strong for MVP)
# ---------------------------------------------------------------------

@dataclass
class KeywordClassifier:
    """
    Simple keyword scoring classifier.

    - keywords_positive: list of terms that increase score
    - keywords_negative: list of terms that decrease score
    - threshold: score >= threshold => positive label
    """
    name: str = "keyword_classifier"
    positive_label: str = "positive"
    negative_label: str = "negative"

    keywords_positive: Tuple[str, ...] = ()
    keywords_negative: Tuple[str, ...] = ()

    threshold: float = 0.55
    weight_pos: float = 1.0
    weight_neg: float = 1.0

    def predict(self, item: Dict[str, Any]) -> Classification:
        title = normalize_ws(str(item.get("title", "") or "")).lower()
        text = normalize_ws(str(item.get("text", "") or "")).lower()
        blob = (title + "\n" + text).strip()

        if not blob:
            return Classification(label=self.negative_label, score=0.0, meta={"reason": "empty_text"})

        pos_hits = [k for k in self.keywords_positive if k.lower() in blob]
        neg_hits = [k for k in self.keywords_negative if k.lower() in blob]

        # raw score = sigmoid-ish from hit counts
        score = 0.5
        score += min(0.45, len(pos_hits) * 0.08 * self.weight_pos)
        score -= min(0.45, len(neg_hits) * 0.10 * self.weight_neg)
        score = max(0.0, min(1.0, score))

        label = self.positive_label if score >= self.threshold else self.negative_label
        return Classification(
            label=label,
            score=score,
            meta={"pos_hits": pos_hits, "neg_hits": neg_hits, "threshold": self.threshold},
        )


# ---------------------------------------------------------------------
# Optional sklearn wrapper (future-ready)
# ---------------------------------------------------------------------

@dataclass
class SklearnTextClassifier:
    """
    Wrapper around a joblib-loaded sklearn pipeline.
    Expected model interface:
      - predict_proba([text]) -> [[p0, p1]]
      - classes_ -> labels

    This stays optional; do not require sklearn in core.
    """
    model_path: str
    name: str = "sklearn_text_classifier"
    text_field: str = "text"
    title_field: str = "title"

    _model: Any = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import joblib  # type: ignore
        except Exception as e:
            raise ImportError("joblib is required to use SklearnTextClassifier") from e
        self._model = joblib.load(self.model_path)

    def predict(self, item: Dict[str, Any]) -> Classification:
        self._load()
        title = normalize_ws(str(item.get(self.title_field, "") or ""))
        text = normalize_ws(str(item.get(self.text_field, "") or ""))
        blob = (title + "\n" + text).strip()

        if not blob:
            return Classification(label="unknown", score=0.0, meta={"reason": "empty_text"})

        model = self._model
        try:
            proba = model.predict_proba([blob])[0]
            classes = getattr(model, "classes_", ["class0", "class1"])
            # assume binary
            best_i = int(proba.argmax())
            label = str(classes[best_i])
            score = float(proba[best_i])
            return Classification(label=label, score=score, meta={"classes": [str(c) for c in classes]})
        except Exception as e:
            return Classification(label="error", score=0.0, meta={"error": f"{type(e).__name__}: {e}"})


# ---------------------------------------------------------------------
# Helper: apply multiple classifiers
# ---------------------------------------------------------------------

def apply_classifiers(item: Dict[str, Any], classifiers: List[Any]) -> Dict[str, Any]:
    """
    Run a list of classifiers and attach outputs under _classifications.
    """
    out = dict(item)
    res: Dict[str, Any] = {}

    for clf in classifiers:
        try:
            pred = clf.predict(item)
            res[getattr(clf, "name", clf.__class__.__name__)] = {
                "label": pred.label,
                "score": pred.score,
                "meta": pred.meta or {},
            }
        except Exception as e:
            res[getattr(clf, "name", clf.__class__.__name__)] = {
                "label": "error",
                "score": 0.0,
                "meta": {"error": f"{type(e).__name__}: {e}"},
            }

    out["_classifications"] = res
    return out
