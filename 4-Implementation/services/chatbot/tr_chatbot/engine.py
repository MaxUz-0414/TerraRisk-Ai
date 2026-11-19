"""
The chatbot's brain: a small text-classification model. No Django in this file.

HOW IT LEARNS ("training"):
  1. Every example question in knowledge.py is turned into numbers with TF-IDF over character groups
     (so it still works with typos like "subscripton").
  2. When a user writes something, we turn it into numbers the same way and find the most similar
     example question. The intent that example belongs to is the answer.
  3. If even the best match is not similar enough (below the threshold) the bot says it is not sure
     instead of guessing.
"""
import hashlib
import json
import pickle
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

MODEL_PATH = Path(__file__).with_name("chatbot_model.pkl")
THRESHOLD = 0.34   # minimum similarity to answer; tuned with `python manage.py train_chatbot`


# Words that carry no meaning for matching. Without this, "what is the weather" looks similar to
# "what is the buffer" just because of "what is the".
FILLER = {"a", "an", "the", "is", "are", "am", "was", "do", "does", "did", "i", "me", "my", "you", "your", "to", "of", "in", "on", "at", "for", "it",
          "this", "that", "what", "whats", "how", "can", "could", "would", "please", "there", "be", "with", "and", "or", "so", "about", "s"}


def normalize(text):
    """Lower-case, keep letters/digits, drop filler words, collapse spaces."""
    words = re.sub(r"[^a-z0-9% ]+", " ", text.lower()).split()
    kept = [w for w in words if w not in FILLER]
    return " ".join(kept or words)  # if everything was filler ("what is this") keep the original words


def knowledge_hash(intents):
    """Changes whenever knowledge.py changes, so an old saved model is never used by mistake."""
    return hashlib.md5(json.dumps([[i["id"], i["questions"]] for i in intents], sort_keys=True).encode()).hexdigest()


class ChatModel:
    def __init__(self, intents):
        self.kb_hash = knowledge_hash(intents)
        self.examples, self.labels = [], []
        for intent in intents:
            for question in intent["questions"]:
                self.examples.append(normalize(question))
                self.labels.append(intent["id"])
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(self.examples)  # this line is the "training"

    def predict(self, text):
        """Return (intent_id, similarity 0..1) for the best matching intent."""
        vec = self.vectorizer.transform([normalize(text)])
        sims = (self.matrix @ vec.T).toarray().ravel()
        best = int(sims.argmax())
        return self.labels[best], float(sims[best])

    def evaluate(self):
        """Leave-one-out test: hide each example, can the others still find its intent?"""
        sims = (self.matrix @ self.matrix.T).toarray()
        correct, wrong = 0, []
        for i, label in enumerate(self.labels):
            sims[i, i] = -1                      # ignore the example itself
            j = int(sims[i].argmax())
            if self.labels[j] == label:
                correct += 1
            else:
                wrong.append((self.examples[i], label, self.labels[j]))
        return {"examples": len(self.labels), "intents": len(set(self.labels)),
                "accuracy": correct / len(self.labels), "mistakes": wrong}


def train_and_save(intents):
    model = ChatModel(intents)
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(model, fh)
    return model


_cached = None


def get_model(intents):
    """Saved model if it is up to date, otherwise train now (takes about a tenth of a second)."""
    global _cached
    if _cached is not None and _cached.kb_hash == knowledge_hash(intents):
        return _cached
    model = None
    if MODEL_PATH.exists():
        try:
            with open(MODEL_PATH, "rb") as fh:
                model = pickle.load(fh)
            if model.kb_hash != knowledge_hash(intents):
                model = None
        except Exception:
            model = None
    _cached = model or ChatModel(intents)
    return _cached
