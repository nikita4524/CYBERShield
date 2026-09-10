"""
URL ML model — TF-IDF (delimiter-tokenized) + Ensemble classifier.

Mirrors ml/phish_model.py's load-or-fallback pattern, but tokenizes the
raw URL string on its structural delimiters (/, -, ., ?, =, &) instead of
treating it as natural-language text — URLs don't have "words", they have
tokens like "hdfc", "verify", "xyz" separated by punctuation.

Gracefully falls back to heuristics-only (services/url_analyzer.py) if
model files are missing — training is a separate, explicit step via
train_models.py --url-only.
"""

import os
import pickle
import re
import warnings
from typing import List, Optional

warnings.filterwarnings("ignore")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Tokens that appear in almost every URL and carry no discriminative
# signal on their own (they'd otherwise dominate/dilute the vocabulary).
_NOISE_TOKENS = {"com", "http", "https", "www", ""}

_DELIMITERS = re.compile(r"[/\-.?=&_]+")


def tokenize_url(url: str) -> List[str]:
    """
    Split a URL into its structural tokens, e.g.
    "hdfc-verify.xyz/login?redirect=x" -> ["hdfc", "verify", "xyz", "login", "redirect", "x"]

    Defined at module level (not a lambda/closure) so the fitted
    TfidfVectorizer that references it can be pickled and reloaded.
    """
    tokens = _DELIMITERS.split(str(url).lower())
    return [t for t in tokens if t and t not in _NOISE_TOKENS]


class URLModel:
    """TF-IDF + Ensemble classifier for URL phishing/malicious detection."""

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = model_dir
        self.vectorizer_path = os.path.join(model_dir, "url_tfidf_vectorizer.pkl")
        self.classifier_path = os.path.join(model_dir, "url_classifier.pkl")

        self.vectorizer = None
        self.classifier = None
        self.is_trained = False

        self._load()

    def _load(self):
        if not SKLEARN_AVAILABLE:
            print("WARNING: scikit-learn not available — URL model disabled, heuristics only")
            return

        if os.path.exists(self.vectorizer_path) and os.path.exists(self.classifier_path):
            try:
                with open(self.vectorizer_path, "rb") as f:
                    self.vectorizer = pickle.load(f)
                with open(self.classifier_path, "rb") as f:
                    self.classifier = pickle.load(f)
                self.is_trained = True
                print("URL model loaded from disk")
            except Exception as e:
                print(f"WARNING: Failed to load URL model: {e} — heuristics only")
        else:
            print("INFO: No trained URL model found — heuristics only")
            print(f"   Run: python train_models.py --url-only")

    def predict_proba(self, url: str) -> Optional[float]:
        """Predict malicious probability for a URL. None if no model is loaded."""
        if not self.is_trained or self.vectorizer is None or self.classifier is None:
            return None
        try:
            features = self.vectorizer.transform([url])
            proba = self.classifier.predict_proba(features)[0]
            classes = list(self.classifier.classes_)
            bad_idx = classes.index(1) if 1 in classes else (len(proba) - 1)
            return float(proba[bad_idx])
        except Exception as e:
            print(f"WARNING: URL model inference error: {e}")
            return None

    def train_baseline(self, urls: List[str], labels: List[int]):
        """
        Train the classifier from data.
        urls: list of raw URL strings
        labels: list of 0 (legitimate) or 1 (malicious/phishing)
        """
        if not SKLEARN_AVAILABLE:
            print("ERROR: Cannot train: scikit-learn not available")
            return False

        print(f"Training URL model on {len(urls)} samples...")

        self.vectorizer = TfidfVectorizer(
            tokenizer=tokenize_url,
            token_pattern=None,
            max_features=15000,
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
        )
        X = self.vectorizer.fit_transform(urls)

        lr = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", random_state=42)
        rf = RandomForestClassifier(
            n_estimators=80, max_depth=20, n_jobs=-1,
            class_weight="balanced", random_state=42,
        )
        self.classifier = VotingClassifier(
            estimators=[("lr", lr), ("rf", rf)], voting="soft", n_jobs=-1,
        )
        self.classifier.fit(X, labels)
        self.is_trained = True

        os.makedirs(self.model_dir, exist_ok=True)
        with open(self.vectorizer_path, "wb") as f:
            pickle.dump(self.vectorizer, f)
        with open(self.classifier_path, "wb") as f:
            pickle.dump(self.classifier, f)

        print(f"URL model trained and saved to {self.model_dir}")
        return True


# Singleton instance
url_model = URLModel()