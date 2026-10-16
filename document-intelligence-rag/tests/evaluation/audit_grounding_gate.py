import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
os.environ['VECTOR_STORE_BACKEND'] = 'local'

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.retrieval import Retriever, CALIBRATED_CONFIDENCE_THRESHOLD

r = Retriever()

in_domain_queries = [
    "What is abstraction?",
    "What is inheritance?",
    "What are operating system functions?",
    "What is polymorphism?",
    "Give me an example of abstraction.",
]

ood_queries = [
    "What is the culinary history of chocolate in ancient Aztec civilization?",
    "Who won the FIFA World Cup in 2022?",
    "What is quantum computing?",
    "What is the capital of Japan?",
]

print("="*70)
print(f"GROUNDING GATE AUDIT (Threshold: {CALIBRATED_CONFIDENCE_THRESHOLD:.2f})")
print("="*70)

print("\n--- IN-DOMAIN QUERIES (Expected: Accepted, non-empty docs) ---")
for q in in_domain_queries:
    docs = r.search(q)
    top_score = docs[0].get("rerank_score", 0.0) if docs else 0.0
    passed = len(docs) > 0 and top_score >= CALIBRATED_CONFIDENCE_THRESHOLD
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] Query: '{q}' -> Docs: {len(docs)} | Top Score: {top_score:.4f}")

print("\n--- OUT-OF-DOMAIN QUERIES (Expected: Refused, 0 docs) ---")
for q in ood_queries:
    docs = r.search(q)
    refused = len(docs) == 0
    status = "PASS" if refused else "FAIL (LEAKAGE)"
    top_score = docs[0].get("rerank_score", 0.0) if docs else 0.0
    print(f"[{status}] Query: '{q}' -> Docs: {len(docs)} | Top Score: {top_score:.4f}")
    if not refused:
        for i, d in enumerate(docs):
            txt = ' '.join((d.get('text') or '').split()[:20])
            print(f"   [Doc {i+1}] {d.get('source')} (p.{d.get('page')}) Score={d.get('rerank_score', 0):.4f}: {txt}...")
