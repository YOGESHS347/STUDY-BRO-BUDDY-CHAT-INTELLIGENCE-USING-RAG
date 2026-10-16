"""
Benchmark runner for Advanced RAG v2.
Evaluates retrieval quality, precision, recall, MRR, groundedness, and latency across Categories A through J.
Outputs structured JSON reports and console comparison tables.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure project paths are in sys.path
EVAL_DIR = Path(__file__).resolve().parent
RAG_DIR = EVAL_DIR.parent.parent
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

# Ensure local reference backend is used for evaluation
os.environ["VECTOR_STORE_BACKEND"] = "local"

from retrieval.retrieval import Retriever, QueryAwareReranker
from generation.generation import Generator
from tests.evaluation.eval_dataset import EVALUATION_DATASET, TestCase

logger = logging.getLogger(__name__)


def evaluate_query(
    retriever: Retriever,
    generator: Optional[Generator],
    test_case: TestCase,
    include_generation: bool = False,
) -> Dict[str, Any]:
    """Evaluates a single test case through the retrieval and optional generation pipeline."""
    start_time = time.perf_counter()

    query = test_case.query

    # Step 1: Preprocessing & Decomposition
    t0 = time.perf_counter()
    normalized_query = retriever.normalize_query(query)
    
    # Check if conversation history is available for follow-up
    conv_history = test_case.conversation_history
    if conv_history and hasattr(retriever, "contextualize_query"):
        contextualized_query = retriever.contextualize_query(normalized_query, conv_history)
    else:
        contextualized_query = normalized_query

    sub_queries = retriever.decompose_query(contextualized_query)
    preprocess_ms = (time.perf_counter() - t0) * 1000.0

    # Step 2: Retrieval & Reranking
    t1 = time.perf_counter()
    try:
        # Search via retriever (local reference database)
        if hasattr(retriever, "search_with_context") and conv_history:
            docs = retriever.search_with_context(query, conversation_history=conv_history)
        else:
            docs = retriever.search(contextualized_query)
    except Exception as e:
        logger.exception("Retrieval error on query '%s': %s", query, e)
        docs = []
    retrieval_ms = (time.perf_counter() - t1) * 1000.0

    # Step 3: Optional Generation
    answer = ""
    gen_ms = 0.0
    if include_generation and generator:
        t2 = time.perf_counter()
        try:
            answer = generator.generate(query, docs)
        except Exception as e:
            answer = f"[ERROR] {e}"
        gen_ms = (time.perf_counter() - t2) * 1000.0

    total_latency_ms = (time.perf_counter() - start_time) * 1000.0

    # Metrics evaluation
    retrieved_sources = [d.get("source") for d in docs if d.get("source")]
    top_doc = docs[0] if docs else {}
    top_source = top_doc.get("source", "None")
    top_page = top_doc.get("page", None)
    top_semantic_score = float(top_doc.get("semantic_score", 0.0))
    top_rerank_score = float(top_doc.get("rerank_score", 0.0))
    
    # Check code presence in top doc
    top_text = top_doc.get("text", "")
    code_score = QueryAwareReranker.contains_code_features(top_text)
    has_code_features = code_score >= 0.40

    # Concept recall
    combined_text = " ".join([d.get("text", "") for d in docs]).lower()
    concepts_found = [
        c for c in test_case.expected_concepts
        if c.lower() in combined_text
    ]
    concept_coverage = (
        len(concepts_found) / len(test_case.expected_concepts)
        if test_case.expected_concepts else 1.0
    )

    # Expected source matching
    expected_sources = test_case.expected_sources or []
    first_rank_relevant = None
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0

    if expected_sources:
        for idx, d in enumerate(docs):
            d_src = d.get("source", "")
            if any(exp in d_src for exp in expected_sources):
                if first_rank_relevant is None:
                    first_rank_relevant = idx + 1
                if idx == 0:
                    hits_at_1 = 1
                if idx < 3:
                    hits_at_3 += 1
                if idx < 5:
                    hits_at_5 += 1

    reciprocal_rank = 1.0 / first_rank_relevant if first_rank_relevant else 0.0
    precision_at_3 = (hits_at_3 / min(3, len(docs))) if docs else 0.0
    precision_at_5 = (hits_at_5 / min(5, len(docs))) if docs else 0.0

    # Grounding refusal correctness
    is_refusal = (len(docs) == 0) or ("the provided documents do not contain enough information" in answer.lower())
    refusal_correct = (test_case.expected_refusal == is_refusal)

    # Classification status
    if test_case.is_out_of_domain:
        if len(docs) == 0 or is_refusal:
            status = "REFUSAL_SUCCESS"
        else:
            status = "OUT_OF_DOMAIN_LEAK"
    elif not docs:
        status = "NO_RELEVANT_CONTEXT"
    elif expected_sources and not first_rank_relevant:
        status = "SOURCE_MISMATCH"
    else:
        status = "SUCCESS"

    return {
        "id": test_case.id,
        "category": test_case.category,
        "query": query,
        "normalized_query": normalized_query,
        "decomposed_queries": sub_queries,
        "candidate_count": len(docs),
        "top_source": top_source,
        "top_page": top_page,
        "top_semantic_score": round(top_semantic_score, 4),
        "top_rerank_score": round(top_rerank_score, 4),
        "has_code_features": has_code_features,
        "code_score": round(code_score, 4),
        "concepts_expected": test_case.expected_concepts,
        "concepts_found": concepts_found,
        "concept_coverage": round(concept_coverage, 4),
        "mrr": round(reciprocal_rank, 4),
        "precision_at_1": hits_at_1,
        "precision_at_3": round(precision_at_3, 4),
        "precision_at_5": round(precision_at_5, 4),
        "preprocess_latency_ms": round(preprocess_ms, 2),
        "retrieval_latency_ms": round(retrieval_ms, 2),
        "total_latency_ms": round(total_latency_ms, 2),
        "status": status,
        "answer": answer,
        "is_refusal": is_refusal,
        "refusal_correct": refusal_correct,
    }


def run_benchmark(
    include_generation: bool = False,
    output_filename: str = "baseline_benchmark.json"
) -> Dict[str, Any]:
    """Runs the full evaluation dataset and computes aggregate metrics."""
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n" + "=" * 75)
    print(f"STARTING RAG BENCHMARK EVALUATION (Cases: {len(EVALUATION_DATASET)})")
    print("=" * 75)

    retriever = Retriever()
    generator = Generator() if include_generation else None

    results = []
    for tc in EVALUATION_DATASET:
        print(f"Evaluating [{tc.id}] ({tc.category}): '{tc.query}'...", end=" ", flush=True)
        res = evaluate_query(retriever, generator, tc, include_generation=include_generation)
        print(f"[{res['status']}] Top: {res['top_source']} (p.{res['top_page']}) RR={res['top_rerank_score']} ({res['total_latency_ms']}ms)")
        results.append(res)

    # Compute aggregate metrics
    in_domain = [r for r in results if not r["category"].startswith("Category H") and not r["category"].startswith("Category I")]
    out_domain = [r for r in results if r["category"].startswith("Category H")]
    ambiguous = [r for r in results if r["category"].startswith("Category I")]
    code_cases = [r for r in results if r["category"].startswith("Category C")]

    avg_mrr = sum(r["mrr"] for r in in_domain) / len(in_domain) if in_domain else 0.0
    avg_p1 = sum(r["precision_at_1"] for r in in_domain) / len(in_domain) if in_domain else 0.0
    avg_concept_cov = sum(r["concept_coverage"] for r in in_domain) / len(in_domain) if in_domain else 0.0
    
    ood_refusal_rate = (
        sum(1 for r in out_domain if r["candidate_count"] == 0 or r["is_refusal"]) / len(out_domain)
        if out_domain else 1.0
    )
    
    code_precision = (
        sum(1 for r in code_cases if r["has_code_features"]) / len(code_cases)
        if code_cases else 0.0
    )

    avg_latency = sum(r["total_latency_ms"] for r in results) / len(results) if results else 0.0

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_queries": len(results),
        "in_domain_queries": len(in_domain),
        "out_of_domain_queries": len(out_domain),
        "mean_reciprocal_rank_mrr": round(avg_mrr, 4),
        "precision_at_1": round(avg_p1, 4),
        "concept_coverage": round(avg_concept_cov, 4),
        "ood_rejection_rate": round(ood_refusal_rate, 4),
        "code_intent_precision": round(code_precision, 4),
        "mean_latency_ms": round(avg_latency, 2),
        "results": results,
    }

    # Save output JSON
    logs_dir = RAG_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    report_path = logs_dir / output_filename
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 75)
    print("EVALUATION SUMMARY")
    print("=" * 75)
    print(f"Total Queries Evaluated : {len(results)}")
    print(f"In-Domain MRR            : {summary['mean_reciprocal_rank_mrr']:.4f}")
    print(f"Precision@1 (Top-1 Acc)  : {summary['precision_at_1']:.4f}")
    print(f"Concept Coverage         : {summary['concept_coverage'] * 100:.1f}%")
    print(f"OOD Refusal Rate         : {summary['ood_rejection_rate'] * 100:.1f}%")
    print(f"Code Intent Precision    : {summary['code_intent_precision'] * 100:.1f}%")
    print(f"Mean Latency             : {summary['mean_latency_ms']:.2f} ms")
    print(f"Report saved to          : {report_path}")
    print("=" * 75 + "\n")

    return summary


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "baseline_benchmark.json"
    gen_flag = "--gen" in sys.argv
    run_benchmark(include_generation=gen_flag, output_filename=out_file)
