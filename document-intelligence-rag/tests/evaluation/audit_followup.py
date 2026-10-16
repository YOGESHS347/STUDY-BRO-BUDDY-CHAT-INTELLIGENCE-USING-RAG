import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
os.environ['VECTOR_STORE_BACKEND'] = 'local'

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.retrieval import Retriever

r = Retriever()

conversations = [
    (
        "Conversation 1: Abstraction follow-up",
        [
            {"role": "user", "content": "What is abstraction?"},
            {"role": "assistant", "content": "Abstraction refers to the act of representing essential features without including background details."}
        ],
        "Give me an example."
    ),
    (
        "Conversation 2: Inheritance follow-up",
        [
            {"role": "user", "content": "What is inheritance?"},
            {"role": "assistant", "content": "Inheritance is the capability of a class to derive properties and characteristics from another class."}
        ],
        "Show me code."
    ),
    (
        "Conversation 3: Encapsulation follow-up",
        [
            {"role": "user", "content": "What is encapsulation?"},
            {"role": "assistant", "content": "Encapsulation is the wrapping up of data and functions into a single unit called class."}
        ],
        "Explain it with an example."
    ),
]

print("=" * 70)
print("FOLLOW-UP CONTEXT RESOLUTION VERIFICATION:")
print("=" * 70)

for label, history, follow_up in conversations:
    contextualized = r.contextualize_query(follow_up, history)
    docs = r.search(follow_up, conversation_history=history)
    print(f"{label}")
    print(f"  Prior query: '{history[0]['content']}'")
    print(f"  Follow-up input: '{follow_up}'")
    print(f"  Contextualized query: '{contextualized}'")
    print(f"  Retrieved count: {len(docs)}")
    if docs:
        top = docs[0]
        print(f"  Top-1: {top.get('source')} (Page {top.get('page')}) Score={top.get('rerank_score', 0):.4f}")
        snippet = ' '.join(top.get('text', '').split()[:20])
        print(f"  Snippet: {snippet}...")
    print("-" * 50)
