import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
os.environ['VECTOR_STORE_BACKEND'] = 'local'

from retrieval.retrieval import Retriever
from generation.generation import Generator

r = Retriever()
g = Generator()

q = "Show me the Payment abstraction example."
print("Testing Query:", q)
docs = r.search(q)
print(f"Retrieved docs: {len(docs)}")
for i, d in enumerate(docs):
    print(f"[{i+1}] {d.get('source')} Page {d.get('page')} (Score: {d.get('rerank_score', 0):.4f})")
    print(d.get("text", "")[:300])
    print("-" * 50)

ans = g.generate(q, docs)
print("ANSWER:\n", ans)
