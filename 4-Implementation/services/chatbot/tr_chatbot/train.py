"""Train the chatbot on knowledge.py, save it and print a quality report:  python -m tr_chatbot.train"""
from . import engine
from .knowledge import INTENTS


def main():
    model = engine.train_and_save(INTENTS)
    report = model.evaluate()
    print(f"Trained on {report['examples']} example questions in {report['intents']} topics.")
    print(f"Saved model: {engine.MODEL_PATH}")
    print(f"Leave-one-out accuracy: {report['accuracy']:.0%} (strict test: each question is hidden while the bot tries to find its topic).")
    for question, wanted, got in report["mistakes"][:15]:
        print(f"  '{question}' should be {wanted}, bot says {got}")


if __name__ == "__main__":
    main()
