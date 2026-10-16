from retrieval.retrieval import Retriever

retriever = Retriever(top_k_per_query=5, final_per_query=3)

queries = [
    "What is inheritance in Python?",
    "What is an operating system?",
    "What is encapsulation?",
]

for query in queries:
    print()
    print("=" * 60)
    print(f"QUERY: {query}")
    print("=" * 60)
    docs = retriever.search(query)
    print("\nRANKED RESULTS:")
    for i, doc in enumerate(docs, start=1):
        print()
        print(f"Rank {i}:")
        print(f"  Rerank Score   : {doc.get('rerank_score', 0):.4f}")
        print(f"  Semantic Score : {doc.get('semantic_score', 0):.4f}")
        print(f"  Score (compat) : {doc.get('score', 0):.4f}")
        print(f"  Source         : {doc.get('source')}")
        print(f"  Page           : {doc.get('page', 'N/A')}")
        text_preview = doc.get("text", "").replace("\n", " ").strip()[:250]
        print(f"  Text Preview   : {text_preview}...")
