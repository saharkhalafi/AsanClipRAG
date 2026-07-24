import csv
from pathlib import Path
from app2.firewall.semantic_intent import SemanticIntentDetector


DATASET_PATH = Path("app2/tests/Data_Test/semantic_eval.csv")


def load_dataset():
    with open(DATASET_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TrackingEmbedder:
    def __init__(self):
        self.call_count = 0

    def embed(self, text: str):
        self.call_count += 1
        return type("V", (), {"tolist": lambda self: [0.01] * 128})()


def run_evaluation(detector, cases):
    total = len(cases)

    correct = 0
    fp = 0
    fn = 0
    reason_mismatch = 0
    field_mismatch = 0

    embedding_calls = detector.embedder.call_count if detector.embedder else 0
    embedding_triggered = 0

    for c in cases:
        before = detector.embedder.call_count if detector.embedder else 0

        result = detector.detect(c["query"])

        after = detector.embedder.call_count if detector.embedder else 0

        if after > before:
            embedding_triggered += 1

        expected_ok = c["expected_ok"].lower() == "true"
        expected_reason = c.get("expected_reason", "")
        expected_field = c.get("expected_best_field", "")

        if result["ok"] == expected_ok:
            correct += 1
        else:
            if result["ok"] and not expected_ok:
                fp += 1
            if not result["ok"] and expected_ok:
                fn += 1

        if expected_reason and result.get("reason") != expected_reason:
            reason_mismatch += 1

        if expected_field and result.get("best_field") != expected_field:
            field_mismatch += 1

    return {
        "total": total,
        "accuracy": correct / total if total else 0,
        "fp": fp,
        "fn": fn,
        "reason_mismatch": reason_mismatch,
        "field_mismatch": field_mismatch,
        "embedding_calls": embedding_calls,
        "embedding_triggered": embedding_triggered,
    }


def test_semantic_intent_evaluation(capsys):

    embedder = TrackingEmbedder()

    detector = SemanticIntentDetector(
        catalog={
           "product_names": [
            "ویدیو تولد مبارک",
            "استوری تولد",
            "قالب اینستاگرام",
            "قالب یوتیوب",
        ],
        "occasions": [
            "تولد",
            "سال نو",
            "تبریک",
            "عید",
            "کریسمس",
            "سالگرد",
            "عروسی",
            "مناسبت",
            "روز مادر",
            "روز پدر",

        ],
        "product_types": [
            "ویدیو",
            "قالب",
            "استوری",
            "کلیپ",
        
        ],
        "platforms": [
            "اینستاگرام",
            "یوتیوب",
            "لینکدین",
        ]
        },
        embedder=embedder,
        db=None
    )

    cases = load_dataset()

    report = run_evaluation(detector, cases)

    output = f"""
📊 SemanticIntent Evaluation Report
----------------------------------
Total cases        : {report['total']}
Accuracy           : {report['accuracy']:.3f}
False Positives    : {report['fp']}
False Negatives    : {report['fn']}
Reason mismatch    : {report['reason_mismatch']}
Field mismatch     : {report['field_mismatch']}
Embedding calls    : {report['embedding_calls']}
Embedding triggered: {report['embedding_triggered']}
----------------------------------
"""

    # 🔥 مهم: این باعث میشه pytest نشون بده
    print(output)

    # optional: اگر خواستی assert
    assert report["accuracy"] >= 0.80