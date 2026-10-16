import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
os.environ['VECTOR_STORE_BACKEND'] = 'local'

from retrieval.retrieval import Retriever
from generation.generation import Generator

r = Retriever()
g = Generator()

acceptance_queries = [
    ('Test 1: What is abstraction?', 'What is abstraction?', None),
    ('Test 2: Abstraction Code', 'Give me the example code of abstraction.', None),
    ('Test 3: Payment Abstraction', 'Show me the Payment abstraction example.', None),
    ('Test 4: Abstraction with code', 'Explain abstraction with code.', None),
    ('Test 5: Follow-up Example', 'Give me an example.', [
        {'role': 'user', 'content': 'What is abstraction?'},
        {'role': 'assistant', 'content': 'Abstraction refers to the act of representing essential features without including background details.'}
    ]),
    ('Test 6: Multi-part comparison & code', 'Explain abstraction, compare it with encapsulation, and give code examples.', None),
    ('Test 7: Out-of-Domain Refusal', 'What is the culinary history of chocolate in ancient Aztec civilization?', None),
]

for label, q, hist in acceptance_queries:
    print('====================================================')
    print(f'{label}')
    print(f'Query: "{q}"')
    print('====================================================')
    docs = r.search(q, conversation_history=hist)
    print(f'Retrieved docs count: {len(docs)}')
    for i, d in enumerate(docs[:2]):
        print(f'  Doc {i+1}: {d.get("source")} (Page {d.get("page")}) Score={d.get("rerank_score", 0):.4f}')
    ans = g.generate(q, docs)
    print(f'Answer:\n{ans}\n')
