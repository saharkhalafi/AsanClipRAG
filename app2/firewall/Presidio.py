from typing import Any, Dict, List, cast

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

SPACY_MODEL = "en_core_web_sm"


class PIIDetector:
    """
    Lightweight PII detection using Microsoft Presidio.
    """

    def __init__(self) -> None:
        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
            }
        ).create_engine()
        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self.anonymizer = AnonymizerEngine()

        self.entities = [
            "PERSON",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "CREDIT_CARD",
            "IBAN_CODE",
            "LOCATION",
            "IP_ADDRESS",
        ]

    def detect(self, text: str) -> Dict[str, Any]:
        if not text or len(text.strip()) < 3:
            return {
                "has_pii": False,
                "entities": [],
                "score": 0.0,
                "anonymized_text": text,
            }

        results: List[RecognizerResult] = self.analyzer.analyze(
            text=text,
            language="en",
            entities=self.entities,
        )

        entities_found: List[Dict[str, Any]] = []
        max_score = 0.0

        for r in results:
            entities_found.append(
                {
                    "type": r.entity_type,
                    "start": r.start,
                    "end": r.end,
                    "score": round(r.score, 3),
                    "text": text[r.start : r.end],
                }
            )
            max_score = max(max_score, r.score)

        if results:
            anonymized = self.anonymizer.anonymize(
                text=text,
                analyzer_results=cast(Any, results),
                operators={
                    "DEFAULT": OperatorConfig(
                        "replace",
                        {"new_value": "<PII>"},
                    )
                },
            )
            anonymized_text = anonymized.text
        else:
            anonymized_text = text

        return {
            "has_pii": bool(results),
            "entities": entities_found,
            "score": round(max_score, 3),
            "anonymized_text": anonymized_text,
        }

    def check(self, text: str) -> Dict[str, Any]:
        """Match other firewall detectors: ok/reason + detection details."""
        result = self.detect(text)
        return {
            "ok": not result["has_pii"],
            "reason": "pii_detected" if result["has_pii"] else "ok",
            **result,
        }
