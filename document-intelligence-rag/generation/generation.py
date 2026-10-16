import logging
from typing import List, Dict, Any

from openai import OpenAI, APIConnectionError, APITimeoutError, APIError

from config import (
    LLM_MODEL_NAME,
    LLM_SERVER_URL,
    MAX_TOKENS,
    TEMPERATURE,
)


logger = logging.getLogger(__name__)


class Generator:
    """
    RAG Answer Generator using local OpenAI-compatible LLM server (Qwen3-4B).
    Enforces strict grounding against retrieved document context.
    """

    def __init__(
        self,
        model_name: str = LLM_MODEL_NAME,
        server_url: str = LLM_SERVER_URL,
    ):
        logger.info("Initializing Generator (model: %s, server: %s)", model_name, server_url)

        self.model_name = model_name
        self.server_url = server_url

        try:
            self.client = OpenAI(
                base_url=server_url,
                api_key="not-needed",
                timeout=60.0,
            )
            logger.info("Generator client initialized.")
        except Exception as error:
            logger.exception("Failed to initialize Generator OpenAI client: %s", error)
            raise RuntimeError(f"Generator client initialization failed: {error}") from error

    # ---------------------------------------------------------
    # BUILD CONTEXT
    # ---------------------------------------------------------

    def build_context(
        self,
        documents: List[Dict[str, Any]],
    ) -> str:
        """
        Formats retrieved documents into structured context blocks for the LLM.
        """
        context_parts = []

        for index, document in enumerate(documents, start=1):
            source = document.get("source", "Unknown")
            page = document.get("page", None)
            text = (document.get("text", "") or "").strip()

            if not text:
                continue

            # Bound individual chunk size to prevent context blowup
            if len(text) > 1500:
                text = text[:1500] + "..."

            location = source
            if page is not None:
                location += f", Page {page}"

            header = f"[Document {index} | Source: {location}]"
            context_parts.append(f"{header}\n{text}")

        return "\n\n".join(context_parts)

    # ---------------------------------------------------------
    # GENERATE
    # ---------------------------------------------------------

    def generate(
        self,
        question: str,
        documents: List[Dict[str, Any]],
    ) -> str:
        """
        Generates a strictly grounded answer to the user's question based ONLY
        on the retrieved documents.
        """
        if not documents:
            logger.warning("No documents provided for generation.")
            return "The provided documents do not contain enough information to answer this question."

        context = self.build_context(documents)

        if not context.strip():
            logger.warning("Document context is empty.")
            return "The provided documents do not contain enough information to answer this question."

        system_prompt = """You are a strictly grounded, factual document question-answering assistant.

Your task is to answer the user's question using ONLY the facts and explanations present in the retrieved document context below.

STRICT GROUNDING GUIDELINES:
1. FACTUAL STRICTNESS: Rely EXCLUSIVELY on the provided document context. Treat retrieved context as your ONLY factual knowledge source. Do NOT use outside knowledge, unstated assumptions, or external facts.
2. NO FABRICATED EXAMPLES OR CLAIMS: Do NOT invent examples, code snippets, syntax, or classifications that are not explicitly present in the context. No external/general model knowledge should be introduced as factual information.
3. OBJECT-ORIENTED CONCEPTS & CODE MECHANISMS:
Recognize that object-oriented concepts (such as data abstraction, inheritance, polymorphism, and encapsulation) are implemented in programming languages via language constructs:
- Data abstraction is implemented via abstract classes, pure virtual functions, and interfaces that specify member function signatures while hiding implementation details.
- Encapsulation is implemented via classes with private/protected data members and public member functions.
- Inheritance is implemented via base and derived classes (e.g. `class Derived : public Base`).
When the user asks for code explaining or demonstrating an object-oriented concept (e.g., "abstraction with code"), explain the relevant language mechanism and present the complete grounded code examples from the retrieved context. Do not refuse simply because the code uses language keywords (like `class Base`, `virtual void show() = 0;`, `Abstract Class`) rather than repeating the word "abstraction" in the code.
4. HANDLING PARTIAL INFORMATION & LANGUAGE QUALIFIERS: If the documents explain a general concept but omit specific details requested by the user (like "in Python" or specific language syntax), DO NOT reject the question entirely. Instead, answer the supported portion, explicitly state what specific details are not provided by the documents, and do NOT provide language-specific syntax or claims from general knowledge.
5. TERMINOLOGY MISMATCH: When the user's wording differs from the terminology used in the retrieved document context, do NOT treat that difference alone as a reason to refuse the answer or return an empty response. Instead:
(1) Acknowledge the terminology difference.
(2) Explain the relevant information using the document's terminology.
(3) Clearly identify if the user's exact terminology is not used by the document (Note: you can skip this for simple acronyms like 'OOP').
(4) Never introduce unsupported facts or infer that terms are equivalent unless context establishes it.
For example, for: "What are the pillars of OOPS?" and retrieved context containing: "BASIC CONCEPTS OF OBJECTS ORIENTED PROGRAMMING", the model should produce an answer along the lines of: "The document does not use the term 'pillars'. Instead, it presents the basic concepts of object-oriented programming. These include Objects, Classes, Data Abstraction, Data Encapsulation, Inheritance, Polymorphism, Dynamic Binding, and Message Passing." Do NOT say that these are "the four pillars". Do NOT add general textbook knowledge about the four pillars. Do NOT claim the document uses the word "pillars". Do NOT invent relationships that the document does not state.
6. ACRONYMS: Never infer or expand an acronym (e.g., "OOPS") unless that expansion is explicitly present in the retrieved context. Do NOT invent an expansion. If it's not defined, state that it's not explicitly defined in the context.
7. MISSING INFORMATION: Only if the document context contains absolutely NO relevant information to answer any part of the question, state clearly: "The provided documents do not contain enough information to answer this question."
8. ACCURACY: Faithfully preserve the definitions, terms, and meaning given in the source text.
9. NO CITATIONS / INTERNAL LEAKS: Do NOT write "Document 1", "Document 2", "Document X", "Source 1", filenames, page numbers, "chunks", "embeddings", "vector database", "Qdrant", or scores in your response. Answer the question directly and naturally. Citations are displayed separately by the UI.
10. STRUCTURE: Organize your answer clearly and concisely. Use distinct headings if the question asks about multiple concepts or functions.
11. MARKDOWN & CODE BLOCKS: Format your response using clean, professional Markdown:
- Use markdown headings (##, ###) for major sections.
- Use bullet points and numbered lists for structured points.
- When the retrieved context contains code examples, snippets, or syntax, always output them inside properly fenced code blocks with the appropriate language identifier (e.g. ```cpp, ```python, ```sql), preserving indentation and structure faithfully.
- Use inline code (`like this`) for class names, method names, variables, and keywords.
12. THOROUGHNESS & CODE PRESENTATION: When the retrieved document context contains code examples that answer the user's question, provide the complete grounded code examples with clear explanations of how they demonstrate the concept.
"""


        user_prompt = f"""Retrieved Document Context:
{context}

User Question:
{question}

Please provide an answer strictly grounded in the document context above:"""

        # Context-aware max_tokens budgeting
        # Context window is 4096 tokens; leave a safety buffer of 128 tokens
        estimated_prompt_tokens = (len(system_prompt) + len(user_prompt)) // 4
        safe_max_tokens = max(512, min(MAX_TOKENS, 4096 - estimated_prompt_tokens - 128))

        logger.debug("Dispatching generation request to local LLM server (%s, safe_max_tokens=%d)...", self.model_name, safe_max_tokens)

        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=safe_max_tokens,
                )

                msg = response.choices[0].message
                answer = msg.content

                if answer and answer.strip():
                    logger.info("Answer generated successfully (%d characters).", len(answer))
                    return answer.strip()

                # Fallback for thinking models (e.g. Qwen3) when tokens remain in reasoning_content
                reasoning = getattr(msg, "reasoning_content", None) or ""
                if reasoning and reasoning.strip():
                    logger.info("Content was empty; extracting grounded answer from reasoning_content (%d chars).", len(reasoning))
                    # If reasoning contains a formatted answer section, extract from there
                    import re
                    match = re.search(r"(?:###|\*\*|Based on the provided|According to the document).*$", reasoning, flags=re.DOTALL)
                    if match and len(match.group(0)) > 100:
                        return match.group(0).strip()
                    return reasoning.strip()

                logger.warning("LLM returned an empty completion (attempt %d/2).", attempt + 1)
                import time
                time.sleep(1.0)

            except (APIConnectionError, APITimeoutError) as conn_error:
                logger.exception("Connection or timeout error while contacting local LLM server: %s", conn_error)
                if attempt == 1:
                    return "[ERROR] Unable to generate an answer. Please make sure the local LLM server is running."
                import time
                time.sleep(1.0)

            except APIError as api_error:
                logger.exception("OpenAI API error during generation: %s", api_error)
                if attempt == 1:
                    return f"[ERROR] Generation server returned an error: {api_error.message if hasattr(api_error, 'message') else api_error}"
                import time
                time.sleep(1.0)

            except Exception as error:
                logger.exception("Unexpected error during answer generation: %s", error)
                if attempt == 1:
                    return "[ERROR] An unexpected error occurred while generating the answer. Please try again."
                import time
                time.sleep(1.0)

        return "[ERROR] Generation failed: The LLM returned an empty response."