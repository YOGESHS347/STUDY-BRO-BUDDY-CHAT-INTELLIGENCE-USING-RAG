import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
os.environ['VECTOR_STORE_BACKEND'] = 'local'

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.retrieval import Retriever, QueryAwareReranker

r = Retriever()
queries = [
    'Give me the example code of abstraction.',
    'Show me the Payment abstraction example.',
    'Explain abstraction with code.',
    'Give me an example of inheritance.',
    'Give me an example of encapsulation.',
    'Give me an example of polymorphism.',
]

print('='*70)
print('CODE INTENT RETRIEVAL VERIFICATION (6 QUERIES):')
print('='*70)

for q in queries:
    docs = r.search(q)
    print(f'QUERY: "{q}"')
    print(f'  Retrieved docs: {len(docs)}')
    if docs:
        top = docs[0]
        src = top.get('source')
        pg = top.get('page')
        sem = top.get('semantic_score', 0)
        rerank = top.get('rerank_score', 0)
        code_score = QueryAwareReranker.contains_code_features(top.get('text', ''))
        print(f'  Top-1: {src} (Page {pg}) | Sem: {sem:.4f} | Rerank: {rerank:.4f} | CodeScore: {code_score:.2f}')
        snippet = ' '.join(top.get('text', '').split()[:25])
        print(f'  Snippet: {snippet}...')
    print('-'*50)
