import sys
import logging

from config import (
    setup_logging,
    TOP_K_PER_QUERY,
    FINAL_PER_QUERY,
)
from retrieval.retrieval import Retriever, extract_clean_citations
from generation.generation import Generator


logger = logging.getLogger(__name__)


def display_sources(documents) -> None:
    """
    Displays clean, formatted source citations for the retrieved documents.
    """
    citations = extract_clean_citations(documents)

    if citations:
        print()
        print("=" * 60)
        print("SOURCES")
        print("=" * 60)
        for citation in citations:
            print(f"- {citation}")


def main():
    # Ensure Windows console handles UTF-8 cleanly
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Setup centralized logging (writes debug to logs/rag.log, warnings to console)
    setup_logging()

    print()
    print("=" * 60)
    print("DOCUMENT INTELLIGENCE RAG")
    print("=" * 60)

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------
    try:
        retriever = Retriever(
            top_k_per_query=TOP_K_PER_QUERY,
            final_per_query=FINAL_PER_QUERY,
        )
        generator = Generator()
    except Exception as error:
        logger.exception("Application initialization failed: %s", error)
        print(f"\n[ERROR] System initialization failed: {error}")
        return

    print()
    print("=" * 60)
    print("RAG SYSTEM READY")
    print("=" * 60)
    print()

    # ---------------------------------------------------------
    # INTERACTIVE CLI LOOP
    # ---------------------------------------------------------
    while True:
        try:
            question = input("Ask a question (or type 'exit'): ").strip()

            if not question:
                print("Please enter a non-empty question.\n")
                continue

            if question.lower() in {"exit", "quit"}:
                print("\nExiting RAG system. Goodbye!")
                break

            # -----------------------------------------------------
            # RETRIEVAL STAGE
            # -----------------------------------------------------
            try:
                retrieved_documents = retriever.search(question)
            except Exception as search_error:
                logger.exception("Retrieval failed for query '%s': %s", question, search_error)
                print("\n[ERROR] Unable to retrieve relevant documents. Please check vector database status.\n")
                continue

            if not retrieved_documents:
                print("\nThe provided documents do not contain enough information to answer this question.\n")
                continue

            # -----------------------------------------------------
            # GENERATION STAGE
            # -----------------------------------------------------
            try:
                answer = generator.generate(
                    question=question,
                    documents=retrieved_documents,
                )
            except Exception as gen_error:
                logger.exception("Generation error for query '%s': %s", question, gen_error)
                print("\n[ERROR] Unable to generate an answer. Please make sure the local LLM server is running.\n")
                continue

            # -----------------------------------------------------
            # OUTPUT ANSWER & SOURCES
            # -----------------------------------------------------
            print()
            print("=" * 60)
            print("ANSWER")
            print("=" * 60)
            print(answer)

            display_sources(retrieved_documents)
            print()

        except KeyboardInterrupt:
            print("\n\nSession interrupted. Exiting RAG system...")
            break
        except Exception as loop_error:
            logger.exception("Unexpected error in main CLI loop: %s", loop_error)
            print(f"\n[ERROR] An unexpected error occurred: {loop_error}\n")


if __name__ == "__main__":
    main()