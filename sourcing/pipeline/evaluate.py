import json
import os
import random
from pathlib import Path

from deepeval.metrics import GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from google import genai

from db import batch, get_boms, get_supplier_products_enriched
from text2product import GEMINI_MODEL, html_to_text

SUPPLIER_PRODUCTS_DIR = Path(__file__).parent.parent / "data" / "supplier_products"

def _build_product_file_index() -> dict[tuple[str, str], Path]:
    """Maps (supplier_name, sku) -> HTML path using supplier_id + product_id from the DB."""
    enriched = get_supplier_products_enriched()
    index: dict[tuple[str, str], Path] = {}
    for p in enriched:
        sid = p["supplier_id"]
        pid = p["product_id"]
        candidates = list(SUPPLIER_PRODUCTS_DIR.glob(f"{sid}_*_{pid}_*.html"))
        if candidates:
            index[(p["supplier_name"], p["sku"])] = candidates[0]
    return index


class GeminiJudge(DeepEvalBaseLLM):
    def __init__(self):
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        # call super after _client is set (parent __init__ calls load_model)
        super().__init__(model=GEMINI_MODEL)

    def load_model(self):
        return self._client

    def generate(self, prompt: str, schema=None) -> str:
        response = self._client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text

    async def a_generate(self, prompt: str, schema=None) -> str:
        return self.generate(prompt, schema)

    def get_model_name(self) -> str:
        return GEMINI_MODEL


_METRIC: GEval | None = None


def _get_metric() -> GEval:
    global _METRIC
    if _METRIC is None:
        _METRIC = GEval(
            name="Supplier Assignment Quality",
            criteria=(
                "Evaluate whether the assigned supplier is a good match for the raw material component.\n"
                "INPUT: the produced finished-good SKU and the raw material component SKU being sourced.\n"
                "ACTUAL OUTPUT: the supplier assignment (name, prices, purity, quality).\n"
                "RETRIEVAL CONTEXT: the supplier's product page content.\n\n"
                "The ONLY criterion is: does the supplier's page confirm they sell this raw material "
                "(or a closely equivalent ingredient) suitable for supplement manufacturing?\n"
                "Score close to 1 if yes. Score close to 0 if the page describes a clearly different "
                "product (e.g. finished capsules vs. raw gelatin) or is entirely irrelevant.\n"
                "Do NOT penalise missing purity, quality, or price fields in the output — those may "
                "simply not have been scraped yet and are irrelevant to this judgement."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.RETRIEVAL_CONTEXT,
            ],
            model=GeminiJudge(),
            threshold=0.5,
            async_mode=False,
        )
    return _METRIC



def evaluate_batch(n_samples: int = 10, filters: list | None = None, seed: int | None = None) -> list[dict]:
    """
    Samples n_samples BOMs, runs batch() on each, and uses DeepEval GEval (Gemini judge)
    to score each supplier-component assignment against the supplier's HTML page.

    Returns list of per-BOM dicts: produced_sku, assignments_judged, uncovered, mean_score.
    """
    boms = get_boms()
    rng = random.Random(seed)
    sample = rng.sample(boms, min(n_samples, len(boms)))
    metric = _get_metric()
    file_index = _build_product_file_index()

    results = []
    for bom in sample:
        produced_sku = bom["ProducedSKU"]
        print(f"\n--- {produced_sku} ---")
        result = batch(produced_sku, filters=filters)

        judged = []
        for component_sku, assignment in result["assignments"].items():
            supplier_name = assignment["supplier"] if isinstance(assignment, dict) else assignment

            html_path = file_index.get((supplier_name, component_sku))
            page_text = html_to_text(html_path.read_text(errors="replace")) if html_path else None

            if page_text is None:
                judged.append({
                    "component_sku": component_sku, "supplier": supplier_name,
                    "score": None, "passed": None, "reason": "no HTML",
                })
                continue

            test_case = LLMTestCase(
                input=f"Produced SKU: {produced_sku}\nComponent SKU: {component_sku}",
                actual_output=json.dumps(assignment) if isinstance(assignment, dict) else supplier_name,
                retrieval_context=[page_text[:6000]],
            )
            metric.measure(test_case)
            passed = metric.score >= metric.threshold
            print(f"  {component_sku} → {supplier_name}: {metric.score:.2f} ({'pass' if passed else 'fail'}) — {metric.reason}")
            judged.append({
                "component_sku": component_sku,
                "supplier": supplier_name,
                "score": metric.score,
                "passed": passed,
                "reason": metric.reason,
            })

        scores = [j["score"] for j in judged if j["score"] is not None]
        skipped = sum(1 for j in judged if j["score"] is None)
        mean_score = sum(scores) / len(scores) if scores else None
        results.append({
            "produced_sku": produced_sku,
            "assignments_judged": judged,
            "uncovered": result["uncovered"],
            "mean_score": mean_score,
            "skipped": skipped,
        })
        skip_note = f"  ({skipped} skipped, no HTML)" if skipped else ""
        print(f"  mean: {mean_score:.2f}{skip_note}" if mean_score is not None else f"  mean: n/a{skip_note}")

    scored = [r["mean_score"] for r in results if r["mean_score"] is not None]
    if scored:
        print(f"\nOverall: {sum(scored)/len(scored):.2f}/1.0 across {len(scored)} BOMs")
    return results


