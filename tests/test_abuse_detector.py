import csv
from pathlib import Path

from app2.firewall.abuse_detector import AbuseDetector

DATASET_PATH = Path(__file__).resolve().parent / "Data_Test" / "abuse_eval.csv"


def load_dataset():
    with open(DATASET_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_abuse_detector_evaluation():

    detector = AbuseDetector()
    cases = load_dataset()

    total = len(cases)

    correct = 0
    fp = 0   # false positive
    fn = 0   # false negative

    reason_errors = 0

    for case in cases:
        result = detector.check(case["query"])

        expected_ok = case["expected_ok"].lower() == "true"
        expected_reason = case["expected_reason"]

        # ---- correctness check (main metric)
        if result["ok"] == expected_ok:
            correct += 1
        else:
            if result["ok"] and not expected_ok:
                fp += 1
            if not result["ok"] and expected_ok:
                fn += 1

        # ---- reason correctness (secondary metric)
        if (
            not expected_ok
            and result.get("reason") != expected_reason
        ):
            reason_errors += 1

    accuracy = correct / total
    fp_rate = fp / total
    fn_rate = fn / total

    print("\n📊 AbuseDetector Evaluation Report")
    print(f"Total cases      : {total}")
    print(f"Accuracy         : {accuracy:.3f}")
    print(f"False Positives  : {fp} ({fp_rate:.3f})")
    print(f"False Negatives  : {fn} ({fn_rate:.3f})")
    print(f"Reason errors    : {reason_errors}")

    # production gate
    assert accuracy >= 0.90, f"accuracy too low: {accuracy:.3f}"
