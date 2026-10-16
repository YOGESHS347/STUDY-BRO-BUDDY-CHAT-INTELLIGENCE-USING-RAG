import sys
from qdrant_client import QdrantClient
from retrieval.retrieval import Retriever
from generation.generation import Generator
from config import VECTOR_DB_PATH, COLLECTION_NAME

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    
    retriever = Retriever(top_k_per_query=5, final_per_query=3)
    
    # Check Qdrant count
    count = retriever.client.count(collection_name=COLLECTION_NAME).count
    print(f"Qdrant vector count: {count}\n")
    
    generator = Generator()
    
    queries = [
        "What is OOPS?",
        "What is OOP?",
        "What are the pillars of OOPS?",
        "What is inheritance in Python?",
        "What is encapsulation?",
        "What are the functions of an operating system?",
        "What is the culinary history of chocolate in ancient Aztec civilization?"
    ]
    
    for q in queries:
        print(f"========================================")
        print(f"Testing Query: {q}")
        print(f"========================================")
        docs = retriever.search(q)
        answer = generator.generate(q, docs)
        print(f"Answer:\n{answer}\n")

if __name__ == "__main__":
    main()
