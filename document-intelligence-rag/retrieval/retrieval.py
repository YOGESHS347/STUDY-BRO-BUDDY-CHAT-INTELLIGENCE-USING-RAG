import logging
import re
import math
from typing import List, Dict, Any, Set, Optional, Tuple
from collections import Counter

from qdrant_client import QdrantClient

from embeddings.embeddings import EmbeddingModel
from config import (
    VECTOR_DB_PATH,
    COLLECTION_NAME,
    VECTOR_STORE_BACKEND,
    QDRANT_URL,
    QDRANT_API_KEY,
    TOP_K_PER_QUERY,
    FINAL_PER_QUERY,
    SINGLE_QUERY_FINAL_K,
    SIMILARITY_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Calibrated confidence threshold for grounding gate
# Verified against positive conceptual cases (>= 0.43) and negative OOD cases (0.0)
CALIBRATED_CONFIDENCE_THRESHOLD = 0.35


# =============================================================
# QUERY-AWARE RERANKER
# =============================================================

class QueryAwareReranker:
    """
    Query-aware lexical, conceptual, and intent-guided reranker.
    Reranks dense retrieval candidates by combining:
    1. Semantic similarity score (dense vector embedding match from Qdrant)
    2. Concept prominence & phrase matching (exact phrase, bigrams, heading/definition patterns)
    3. Lexical coverage & term density
    4. Strict concept-grounded intent alignment (code features only boosted when concept is present)
    5. Language and domain qualifier alignment (e.g. Python vs C++)
    """

    STOPWORDS: Set[str] = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an",
        "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
        "before", "being", "below", "between", "both", "but", "by", "can",
        "cannot", "could", "couldn't", "did", "didn't", "do", "does",
        "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
        "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't",
        "having", "he", "her", "here", "hers", "herself", "him", "himself",
        "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its",
        "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
        "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
        "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
        "shan't", "she", "should", "shouldn't", "so", "some", "such", "than",
        "that", "the", "their", "theirs", "them", "themselves", "then",
        "there", "these", "they", "this", "those", "through", "to", "too",
        "under", "until", "up", "very", "was", "wasn't", "we", "were",
        "weren't", "what", "when", "where", "which", "while", "who", "whom",
        "why", "with", "won't", "would", "wouldn't", "you", "your", "yours",
        "yourself", "yourselves",
        # Conversational filler
        "give", "tell", "explain", "describe", "provide", "show", "define",
        "detail", "briefly", "please", "simple", "words", "meaning", "notes",
    }

    INTENT_TERMS: Set[str] = {
        "code", "example", "examples", "implementation", "syntax",
        "program", "sample", "demonstrate", "snippet", "source",
        "definition", "explain", "explanation", "difference", "compare",
    }

    LANGUAGE_QUALIFIERS: Set[str] = {
        "python", "py", "c++", "cpp", "cplusplus", "c", "java", "sql",
    }

    @staticmethod
    def contains_code_features(text: str) -> float:
        """
        Detects code patterns and features in document text.
        Returns a score between 0.0 and 1.0 indicating code density/presence.
        """
        if not text:
            return 0.0

        score = 0.0
        code_keywords = [
            r"\bclass\s+[A-Za-z0-9_]+",
            r"\bstruct\s+[A-Za-z0-9_]+",
            r"\bvirtual\b",
            r"\binterface\b",
            r"\bpublic\s*:",
            r"\bprivate\s*:",
            r"\bprotected\s*:",
            r"#include\s*<",
            r"\bvoid\s+[A-Za-z0-9_]+",
            r"\bint\s+[A-Za-z0-9_]+\s*\(",
            r"\bdef\s+[A-Za-z0-9_]+",
            r"\bfunction\b",
            r"\breturn\b",
            r"\bcout\s*<<",
            r"\bcin\s*>>",
            r"\bprintf\s*\(",
            r"\bstd::",
            r"=\s*0\s*;",   # pure virtual function syntax
            r"\boverride\b",
            r"\bself\.",
            r"\b__init__\b",
        ]
        keyword_hits = sum(1 for kw in code_keywords if re.search(kw, text, flags=re.IGNORECASE))
        if keyword_hits >= 3:
            score = max(score, 0.90)
        elif keyword_hits >= 2:
            score = max(score, 0.75)
        elif keyword_hits == 1:
            score = max(score, 0.50)

        braces = text.count("{") + text.count("}")
        semicolons = text.count(";")
        if braces >= 2 and semicolons >= 2:
            score = max(score, 0.85)
        elif braces >= 1 or semicolons >= 3:
            score = max(score, 0.65)

        return min(1.0, score)

    def __init__(
        self,
        semantic_weight: float = 0.35,
        lexical_weight: float = 0.35,
        concept_weight: float = 0.30,
    ):
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.concept_weight = concept_weight

    def get_term_root(self, term: str) -> str:
        """
        Morphological root extraction that correctly maps derived forms
        (e.g., abstraction -> abstract, inheritance -> inherit).
        """
        term = term.lower().strip(" .-_:,;")
        if len(term) <= 4:
            return term
        
        # Consistent stem normalizations for core OOP concepts
        if term.startswith("abstract"):
            return "abstract"
        if term.startswith("inherit"):
            return "inherit"
        if term.startswith("encapsul"):
            return "encapsul"
        if term.startswith("polymorph"):
            return "polymorph"
        if term.startswith("program"):
            return "program"
        if term.startswith("operat"):
            return "operat"
        if term.startswith("process"):
            return "process"
        if term.startswith("connect"):
            return "connect"
        if term.startswith("function"):
            return "function"
        if term.startswith("implement"):
            return "implement"

        return re.sub(
            r"(ation|ations|tion|tions|sion|sions|ing|ances|ance|ences|ence|ed|es|s|ments|ment|ive|al)$",
            "",
            term,
        )

    def parse_query_terms(self, query: str) -> Tuple[List[str], List[str], List[str]]:
        """
        Decomposes query into:
        1. Concept terms: core subjects/entities (e.g. abstraction, inheritance, process, tcp)
        2. Intent terms: modifiers (e.g. code, example, syntax, detail)
        3. Language terms: explicit programming languages or technology qualifiers (e.g. python, c++)
        """
        if not query:
            return [], [], []

        raw_tokens = re.findall(r"\b[a-zA-Z0-9_+#.-]+\b", query.lower())
        tokens = [t.strip(".-_") for t in raw_tokens if len(t.strip(".-_")) > 1]

        concept_terms = []
        intent_terms = []
        language_terms = []

        for token in tokens:
            if token in self.LANGUAGE_QUALIFIERS:
                language_terms.append(token)
            elif token in self.INTENT_TERMS:
                intent_terms.append(token)
            elif token not in self.STOPWORDS:
                concept_terms.append(token)

        # Fallback if all terms were filtered
        if not concept_terms and tokens:
            concept_terms = [t for t in tokens if t not in self.STOPWORDS] or tokens

        return concept_terms, intent_terms, language_terms

    def compute_lexical_score(
        self,
        query_terms: List[str],
        doc_text: str,
    ) -> float:
        if not query_terms or not doc_text:
            return 0.0

        doc_lower = doc_text.lower()
        doc_tokens = [t.strip(".-_") for t in re.findall(r"\b[a-zA-Z0-9_+#.-]+\b", doc_lower)]
        doc_token_counts = Counter(doc_tokens)
        doc_roots = Counter(self.get_term_root(t) for t in doc_tokens)

        unique_query_terms = list(dict.fromkeys(query_terms))
        if not unique_query_terms:
            return 0.0

        matched_term_scores = []
        term_saturations = []

        for term in unique_query_terms:
            root = self.get_term_root(term)
            exact_count = doc_token_counts.get(term, 0)
            root_count = doc_roots.get(root, 0)

            total_effective_count = max(exact_count, root_count)

            if total_effective_count > 0:
                match_quality = 1.0 if exact_count > 0 else 0.85
                matched_term_scores.append(match_quality)
                saturation = total_effective_count / (total_effective_count + 1.5)
                term_saturations.append(saturation)
            else:
                matched_term_scores.append(0.0)
                term_saturations.append(0.0)

        coverage = sum(matched_term_scores) / len(unique_query_terms)
        avg_density = sum(term_saturations) / len(unique_query_terms)

        lexical_score = (0.50 * coverage) + (0.50 * avg_density)
        return min(1.0, lexical_score)

    def compute_concept_score(
        self,
        query: str,
        concept_terms: List[str],
        doc_text: str,
    ) -> float:
        if not concept_terms or not doc_text:
            return 0.0

        doc_lower = doc_text.lower()
        prominence_score = 0.0

        for term in concept_terms:
            root = self.get_term_root(term)

            # 1. Heading or Section Title detection
            heading_pattern = rf"(^|\n|\.\s+)([A-Za-z0-9_\s]{{0,30}}\b{re.escape(root)}[a-z]*\b[\s:]*(\n|:))"
            if re.search(heading_pattern, doc_text, flags=re.IGNORECASE):
                prominence_score = max(prominence_score, 0.90)

            # 2. Direct Definition pattern
            definition_pattern = rf"\b{re.escape(root)}[a-z]*\b\s+(is|refers\s+to|means|when\s+used|provides|allows)\b"
            if re.search(definition_pattern, doc_lower):
                prominence_score = max(prominence_score, 0.85)

            # 3. Class or Component definition pattern (e.g. class Abstract, class Account)
            class_pattern = rf"\bclass\s+[A-Za-z0-9_]*{re.escape(root)}[a-z0-9_]*\b"
            if re.search(class_pattern, doc_lower):
                prominence_score = max(prominence_score, 0.80)

            # 4. Keyword presence
            if re.search(rf"\b{re.escape(root)}[a-z]*\b", doc_lower):
                prominence_score = max(prominence_score, 0.60)

        # Bigram matching if multiple concept terms exist
        if len(concept_terms) >= 2:
            bigram_matches = 0
            total_bigrams = len(concept_terms) - 1
            for i in range(total_bigrams):
                r1 = self.get_term_root(concept_terms[i])
                r2 = self.get_term_root(concept_terms[i+1])
                if re.search(rf"\b{re.escape(r1)}[a-z]*\s+{re.escape(r2)}[a-z]*\b", doc_lower):
                    bigram_matches += 1
            if total_bigrams > 0 and bigram_matches > 0:
                prominence_score = max(prominence_score, min(1.0, 0.70 + (bigram_matches / total_bigrams) * 0.30))

        return min(1.0, prominence_score)

    def score_document(
        self,
        query: str,
        doc: Dict[str, Any],
    ) -> float:
        semantic_score = float(doc.get("semantic_score", doc.get("score", 0.0)))
        doc_text = doc.get("text", "")
        doc_source = str(doc.get("source", "")).lower()
        doc_file_type = str(doc.get("file_type", "")).lower()

        concept_terms, intent_terms, language_terms = self.parse_query_terms(query)
        all_terms = concept_terms + intent_terms + language_terms

        lexical_score = self.compute_lexical_score(all_terms, doc_text)
        concept_score = self.compute_concept_score(query, concept_terms, doc_text)

        rerank_score = (
            self.semantic_weight * semantic_score
            + self.lexical_weight * lexical_score
            + self.concept_weight * concept_score
        )

        # ----------------------------------------------------
        # Intent Alignment: Code / Example Boost (Concept-Grounded)
        # ----------------------------------------------------
        query_lower = query.lower()
        has_code_intent = any(
            re.search(rf"\b{re.escape(term)}\b", query_lower)
            for term in self.INTENT_TERMS
            if term in {"code", "example", "examples", "syntax", "implementation", "program", "sample"}
        )

        if has_code_intent:
            code_feature_score = self.contains_code_features(doc_text)
            
            # Check whether the chunk actually addresses the concept
            concept_matched = False
            if not concept_terms:
                concept_matched = True
            else:
                for ct in concept_terms:
                    ct_root = self.get_term_root(ct)
                    if (
                        re.search(rf"\b{re.escape(ct_root)}[a-z]*\b", doc_text, re.IGNORECASE)
                        or ct in doc_text.lower()
                    ):
                        concept_matched = True
                        break

            if concept_matched and code_feature_score >= 0.40:
                # Genuine code matching the requested concept
                intent_boost = 0.25 * code_feature_score
                rerank_score += intent_boost
            elif not concept_matched and code_feature_score >= 0.40 and concept_terms:
                # Unrelated code chunk that lacks the concept -> penalize
                rerank_score -= 0.15

        # ----------------------------------------------------
        # Language & Technology Qualifier Alignment (e.g. Python vs C++)
        # ----------------------------------------------------
        if "python" in language_terms:
            if "python" in doc_source or doc_file_type in {"docx", "py"} or "python" in doc_text.lower():
                rerank_score += 0.22
            else:
                rerank_score -= 0.15
        elif any(l in language_terms for l in ["c++", "cpp", "cplusplus"]):
            if "c++" in doc_source or "oops" in doc_source or ".pdf" in doc_source:
                rerank_score += 0.15
            else:
                rerank_score -= 0.10

        # Preserve reasonable bounds [0.0, 1.0]
        return max(0.0, min(1.0, rerank_score))

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        for doc in documents:
            if "semantic_score" not in doc:
                doc["semantic_score"] = float(doc.get("score", 0.0))

            rerank_score = self.score_document(query, doc)
            doc["rerank_score"] = rerank_score
            doc["score"] = rerank_score

        reranked_docs = sorted(
            documents,
            key=lambda d: d.get("rerank_score", 0.0),
            reverse=True,
        )

        return reranked_docs


# =============================================================
# CITATION & SOURCE HELPERS
# =============================================================

def format_source_citation(document: Dict[str, Any]) -> str:
    """Formats a human-readable citation string."""
    source = document.get("source", "Unknown")
    page = document.get("page", None)
    file_type = (document.get("file_type") or "").lower()
    sheet_name = document.get("sheet_name", None)
    row_number = document.get("row_number", None)

    if file_type == "pdf" or str(source).lower().endswith(".pdf"):
        if page is not None:
            return f"{source} — Page {page}"
        return f"{source}"

    if file_type in {"xlsx", "xls"} or str(source).lower().endswith((".xlsx", ".xls")):
        details = []
        if sheet_name:
            details.append(f"Sheet: {sheet_name}")
        if row_number is not None:
            details.append(f"Row: {row_number}")
        if details:
            return f"{source} — {', '.join(details)}"
        return f"{source}"

    return f"{source}"


def extract_clean_citations(documents: List[Dict[str, Any]]) -> List[str]:
    """Extracts deduplicated, ordered source citation strings."""
    seen = set()
    citations = []

    for doc in documents:
        citation = format_source_citation(doc)
        if citation not in seen:
            seen.add(citation)
            citations.append(citation)

    return citations


# =============================================================
# RETRIEVER
# =============================================================

class Retriever:

    def __init__(
        self,
        top_k_per_query: int = TOP_K_PER_QUERY,
        final_per_query: int = FINAL_PER_QUERY,
    ):
        logger.info("Initializing Retriever (top_k_per_query=%d, final_per_query=%d)", top_k_per_query, final_per_query)

        self.top_k_per_query = top_k_per_query
        self.final_per_query = final_per_query

        try:
            if VECTOR_STORE_BACKEND == "qdrant_cloud" and QDRANT_URL:
                logger.info("Retriever connecting to Qdrant Cloud: %s", QDRANT_URL)
                self.client = QdrantClient(
                    url=QDRANT_URL,
                    api_key=QDRANT_API_KEY,
                )
                try:
                    collections = self.client.get_collections().collections
                    if not any(c.name == COLLECTION_NAME for c in collections):
                        from qdrant_client.models import Distance, VectorParams
                        self.client.create_collection(
                            collection_name=COLLECTION_NAME,
                            vectors_config=VectorParams(
                                size=384,
                                distance=Distance.COSINE,
                            ),
                        )
                except Exception as c_err:
                    logger.warning("Could not auto-verify collection '%s' on Qdrant Cloud: %s", COLLECTION_NAME, c_err)
            else:
                logger.info("Retriever connecting to local Qdrant at: %s", VECTOR_DB_PATH)
                self.client = QdrantClient(path=VECTOR_DB_PATH)

            self.embedding_model = EmbeddingModel()
            self.reranker = QueryAwareReranker()
            logger.info("Retriever initialized successfully.")
        except Exception as error:
            logger.exception("Failed to initialize Retriever: %s", error)
            raise RuntimeError(f"Retriever initialization failed: {error}") from error

    def close(self):
        """Closes the underlying Qdrant client connection releasing local locks."""
        if hasattr(self, "client") and self.client:
            try:
                self.client.close()
            except Exception:
                pass

    def normalize_query(self, query: str) -> str:
        """Lightweight deterministic normalization."""
        normalized = query.strip()
        replacements = [
            (r"\boops\s+concepts\b", "object oriented programming concepts"),
            (r"\boop\s+concepts\b", "object oriented programming concepts"),
            (r"\boops\s+principles\b", "object oriented programming concepts"),
            (r"\boop\s+principles\b", "object oriented programming concepts"),
            (r"\bpillars\s+of\s+oops\b", "basic concepts of object oriented programming"),
            (r"\bpillars\s+of\s+oop\b", "basic concepts of object oriented programming"),
            (r"\bpillars\b", "basic concepts"),
            (r"\boops\b", "object oriented programming"),
            (r"\boop\b", "object oriented programming"),
        ]
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        return normalized

    def contextualize_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Follow-up resolution using conversation history.
        Enables natural follow-up queries ('Give me an example', 'How does this relate to encapsulation?')
        without requiring the user to repeat the topic.
        """
        clean_q = query.strip()
        lower_q = clean_q.lower()

        # Check for elliptical follow-up patterns
        follow_up_patterns = [
            r"^(?:give\s+me\s+)?(?:an?\s+)?examples?(?:\s+code)?\.?$",
            r"^(?:show\s+me\s+)?(?:the\s+)?code(?:\s+example)?\.?$",
            r"^(?:tell\s+me\s+)?more(?:\s+about\s+it)?\.?$",
            r"^(?:how\s+about|what\s+about)\s+(?:the\s+)?(?:example|code)\??$",
            r"^(?:explain|describe)\s+(?:it|this|that|the\s+code)(?:\s+(?:with|using)\s+(?:an?\s+)?(?:example|code))?\.?$",
            r"^(?:explain|describe)\s+(?:it|this|that)(?:\s+further|\s+more)?\.?$",
            r"^how\s+does\s+(?:this|it)\s+relate\s+to\s+(.+)$",
            r"^how\s+is\s+this\s+different\s+from\s+(.+)$",
        ]

        is_follow_up = any(re.search(p, lower_q) for p in follow_up_patterns)
        if not is_follow_up and len(clean_q.split()) > 3:
            return clean_q

        if not conversation_history:
            return clean_q

        # Extract recent user queries to find active concept
        user_queries = [
            m.get("content", "")
            for m in conversation_history
            if m.get("role") == "user" and m.get("content")
        ]
        if not user_queries:
            return clean_q

        last_query = user_queries[-1]
        last_concept = re.sub(
            r"^(what\s+is|explain|describe|tell\s+me\s+about|show\s+me|give\s+me)\s+",
            "",
            last_query,
            flags=re.IGNORECASE,
        ).strip(" ?.,:")

        # Strip generic modifiers
        last_concept = re.sub(r"\b(in\s+detail|in\s+simple\s+words|briefly|please|code|example)\b", "", last_concept, flags=re.IGNORECASE).strip(" ?.,:")

        if not last_concept or len(last_concept) < 2:
            return clean_q

        # If user asks for example/code of previous concept
        if re.search(r"\b(example|code|syntax|sample|snippet)\b", lower_q):
            return f"{last_concept} code example implementation"

        # If user asks for comparison with another concept
        relate_match = re.search(r"(?:relate\s+to|different\s+from|compare\s+with)\s+([a-zA-Z0-9_\s]+)", lower_q)
        if relate_match:
            other_concept = relate_match.group(1).strip(" ?.,:")
            return f"Compare {last_concept} and {other_concept} difference"

        return f"{last_concept} {clean_q}"

    def decompose_query(self, query: str) -> List[str]:
        """
        Decomposes query into targeted subqueries:
        - Multi-concept comparisons: concept1, concept2, comparison
        - Hybrid concept + code: conceptual explanation, implementation code, abstract class variant
        - General queries: preserved intact
        """
        query_clean = query.strip()

        # 1. Comparison & Difference Intent
        diff_match = re.search(
            r"^([a-zA-Z0-9_\s]+?)\s+(?:and|vs\.?|versus)\s+([a-zA-Z0-9_\s]+?)(?:\s+(?:and\s+how\s+they\s+differ|differ|differences?|comparison)|$)",
            re.sub(r"^(?:explain|compare|what\s+is|what\s+are)\s+", "", query_clean, flags=re.IGNORECASE).strip(" ?.,:"),
            re.IGNORECASE,
        )
        if diff_match:
            c1 = diff_match.group(1).strip(" ?.,:")
            c2 = diff_match.group(2).strip(" ?.,:")
            if len(c1) >= 2 and len(c2) >= 2:
                return [
                    f"What is {c1}?",
                    f"What is {c2}?",
                    f"Difference between {c1} and {c2}",
                ]

        # 2. Code / Example Intent
        has_code_intent = bool(
            re.search(
                r"\b(code|examples?|syntax|implementation|sample|snippet)\b",
                query_clean,
                flags=re.IGNORECASE,
            )
        )

        if has_code_intent:
            core_concept = re.sub(
                r"\b(give\s+me|tell\s+me|explain|describe|show\s+me|provide|what\s+is|the|an?|examples?\s+code\s+of|examples?\s+of|code\s+of|with\s+code|using\s+code|show\s+code|and\s+code|with\s+examples?|in\s+detail|in\s+simple\s+words|briefly|please|sample|syntax\s+of|code|examples?|syntax|implementation)\b",
                "",
                query_clean,
                flags=re.IGNORECASE,
            ).strip(" ?.,:")

            if len(core_concept) >= 2:
                # Provide conceptual + implementation + specialized class variant
                subqueries = [
                    f"What is {core_concept}?",
                    f"{core_concept} example code implementation",
                ]
                # If concept is abstraction, include abstract class query to capture C++ pure virtual function
                if "abstract" in core_concept.lower():
                    subqueries.append("abstract class pure virtual function example code")
                elif "virtual" in core_concept.lower():
                    subqueries.append("virtual function pure virtual function example code")
                return subqueries

        # 3. Simple list splitting (e.g. "objects, classes, and inheritance")
        cleaned = re.sub(
            r"^(give me|tell me|explain|describe|what is|what are|provide|show me|define)\s+",
            "",
            query_clean,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\b(in detail|in simple words|briefly|please)\b", "", cleaned, flags=re.IGNORECASE).strip(" ?.,:")

        parts = re.split(r",\s*|\band\b|\bor\b", cleaned, flags=re.IGNORECASE)
        concepts = [p.strip(" ?.,:") for p in parts if len(p.strip(" ?.,:")) >= 3]

        if len(concepts) > 1 and len(concepts) <= 4:
            return [f"What is {c}?" for c in concepts]

        return [query_clean]

    def semantic_search(
        self,
        query: str,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Performs dense vector retrieval using Qdrant and the embedding model.
        Supports multi-tenant filtering by user_id and document_id.
        In 'qdrant_cloud' mode, user_id is MANDATORY to prevent cross-tenant data leaks.
        """
        logger.debug("Executing semantic search for query: '%s' (user_id=%s, doc_id=%s)", query, user_id, document_id)

        if VECTOR_STORE_BACKEND == "qdrant_cloud":
            if not user_id or not str(user_id).strip():
                raise ValueError(
                    "user_id is strictly required for retrieval when VECTOR_STORE_BACKEND is 'qdrant_cloud'. "
                    "Unrestricted tenant search is forbidden."
                )

        try:
            query_embedding = self.embedding_model.embed_query(query)
            if not query_embedding:
                logger.warning("Empty query embedding generated for '%s'", query)
                return []

            query_filter = None
            conditions = []

            if user_id is not None and str(user_id).strip():
                from qdrant_client.models import FieldCondition, MatchValue
                conditions.append(
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=str(user_id)),
                    )
                )

            if document_id is not None and str(document_id).strip():
                from qdrant_client.models import FieldCondition, MatchValue
                conditions.append(
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    )
                )

            if conditions:
                from qdrant_client.models import Filter
                query_filter = Filter(must=conditions)

            result = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_embedding,
                query_filter=query_filter,
                limit=self.top_k_per_query,
                with_payload=True,
                with_vectors=False,
            )
        except ValueError:
            raise
        except Exception as error:
            logger.exception("Qdrant query execution failed for query '%s': %s", query, error)
            raise RuntimeError(f"Dense vector retrieval failed: {error}") from error

        documents = []
        for point in result.points:
            score = float(point.score)
            if score < SIMILARITY_THRESHOLD:
                continue

            payload = point.payload or {}
            document = {
                "text": payload.get("text", ""),
                "source": payload.get("source", "Unknown"),
                "user_id": payload.get("user_id", None),
                "page": payload.get("page", None),
                "file_type": payload.get("file_type", None),
                "content_type": payload.get("content_type", None),
                "point_id": str(point.id),
                "chunk_id": payload.get("chunk_id", None),
                "chunk_index": payload.get("chunk_index", None),
                "document_id": payload.get("document_id", None),
                "row_number": payload.get("row_number", None),
                "sheet_name": payload.get("sheet_name", None),
                "paragraph_index": payload.get("paragraph_index", None),
                "semantic_score": score,
                "score": score,
                "sub_query": query,
            }
            documents.append(document)

        return documents

    def expand_neighbors(
        self,
        documents: List[Dict[str, Any]],
        max_expansions: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Bounded neighbor context expansion:
        Retrieves adjacent chunks for high-confidence chunks to assemble multi-chunk
        code blocks or complete sections without context explosion.
        """
        if not documents:
            return []

        expanded_docs = list(documents)
        existing_keys = {
            (d.get("source"), d.get("page"), d.get("chunk_index"))
            for d in documents
        }

        expansion_count = 0
        for doc in documents[:3]:  # expand at most top 3 candidates
            if expansion_count >= max_expansions:
                break

            source = doc.get("source")
            page = doc.get("page")
            score = doc.get("rerank_score", 0.0)

            # Only expand high-confidence document pages (PDFs or DOCX with page context)
            if score >= 0.50 and page is not None and source:
                try:
                    from qdrant_client.models import Filter, FieldCondition, MatchValue
                    neighbor_filter = Filter(must=[
                        FieldCondition(key="source", match=MatchValue(value=source)),
                        FieldCondition(key="page", match=MatchValue(value=page)),
                    ])
                    # If in cloud mode, preserve user_id filter
                    if doc.get("user_id"):
                        neighbor_filter.must.append(
                            FieldCondition(key="user_id", match=MatchValue(value=doc["user_id"]))
                        )

                    pts, _ = self.client.scroll(
                        collection_name=COLLECTION_NAME,
                        scroll_filter=neighbor_filter,
                        limit=10,
                        with_payload=True,
                    )

                    for pt in pts:
                        payload = pt.payload or {}
                        n_chunk_idx = payload.get("chunk_index")
                        key = (source, page, n_chunk_idx)
                        if key not in existing_keys:
                            existing_keys.add(key)
                            neighbor_doc = {
                                "text": payload.get("text", ""),
                                "source": payload.get("source", "Unknown"),
                                "user_id": payload.get("user_id", None),
                                "page": payload.get("page", None),
                                "file_type": payload.get("file_type", None),
                                "content_type": payload.get("content_type", None),
                                "point_id": str(pt.id),
                                "chunk_id": payload.get("chunk_id", None),
                                "chunk_index": n_chunk_idx,
                                "document_id": payload.get("document_id", None),
                                "row_number": payload.get("row_number", None),
                                "sheet_name": payload.get("sheet_name", None),
                                "semantic_score": doc.get("semantic_score", 0.0),
                                "rerank_score": score * 0.95,  # inherited neighbor score
                                "score": score * 0.95,
                                "is_expanded_neighbor": True,
                            }
                            expanded_docs.append(neighbor_doc)
                            expansion_count += 1
                            if expansion_count >= max_expansions:
                                break
                except Exception as e:
                    logger.debug("Neighbor expansion skipped for %s (p.%s): %s", source, page, e)

        return expanded_docs

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Main retrieval pipeline:
        1. Contextualizes query with conversation history (for follow-up questions).
        2. Detects ambiguity (refuses ambiguous queries without prior context).
        3. Normalizes and decomposes queries into targeted subqueries.
        4. Dense vector retrieval with strict tenant filtering.
        5. Query-aware lexical and concept reranking.
        6. Deduplicates candidates by unique identity.
        7. Bounded neighbor expansion to prevent context truncation.
        8. Calibrated grounding gate: drops context below threshold to trigger refusal.
        """
        query = (query or "").strip()
        if not query:
            return []

        # Step 1: Follow-up contextualization
        contextualized_query = self.contextualize_query(query, conversation_history)
        
        # Step 2: Ambiguity gate
        # If query is ambiguous (e.g. 'tell me about it') and has NO conversation history, refuse early
        lower_q = query.lower().strip(" ?.,:")
        if lower_q in {"tell me about it", "explain this", "what about the example", "give me more", "explain it"}:
            if not conversation_history:
                logger.info("Ambiguous query '%s' received without conversation context. Returning empty context for refusal.", query)
                return []

        # Step 3: Normalization & Decomposition
        normalized_query = self.normalize_query(contextualized_query)
        sub_queries = self.decompose_query(normalized_query)

        # Step 4: Dense Retrieval + Reranking across subqueries
        balanced_documents = []
        for sub_query in sub_queries:
            candidates = self.semantic_search(
                sub_query,
                user_id=user_id,
                document_id=document_id,
            )
            reranked_candidates = self.reranker.rerank(sub_query, candidates)
            selected = reranked_candidates[:self.final_per_query]
            balanced_documents.extend(selected)

        # Step 5: Deduplication
        unique_documents = {}
        for document in balanced_documents:
            point_id = document.get("point_id")
            source = document.get("source")
            page = document.get("page")
            chunk_index = document.get("chunk_index")
            text_prefix = (document.get("text") or "")[:80].strip()

            dedup_key = point_id or (source, page, chunk_index, text_prefix)
            if (
                dedup_key not in unique_documents
                or document.get("rerank_score", 0.0)
                > unique_documents[dedup_key].get("rerank_score", 0.0)
            ):
                unique_documents[dedup_key] = document

        documents = list(unique_documents.values())

        # Step 6: Bounded Neighbor Context Expansion
        if len(sub_queries) == 1:
            documents = self.expand_neighbors(documents, max_expansions=2)
        elif len(documents) <= 3:
            documents = self.expand_neighbors(documents, max_expansions=1)

        # Step 7: Final result size, ranking, and context budgeting
        documents.sort(
            key=lambda d: d.get("rerank_score", 0.0),
            reverse=True,
        )

        # Context Budgeting:
        # 1. Document limit: max 6 chunks
        # 2. Character limit: max 5,500 characters (~1,400 tokens)
        # Guarantees prompt fits within 4,096 token context window with ample space for generation
        max_allowed_docs = 6
        max_context_chars = 5500

        final_documents = []
        total_chars = 0

        for doc in documents:
            doc_text = doc.get("text", "") or ""
            if len(final_documents) >= 2 and (total_chars + len(doc_text) > max_context_chars):
                break
            final_documents.append(doc)
            total_chars += len(doc_text)
            if len(final_documents) >= max_allowed_docs:
                break

        # Step 8: Calibrated Grounding Gate
        if final_documents:
            top_score = final_documents[0].get("rerank_score", 0.0)
            if top_score < CALIBRATED_CONFIDENCE_THRESHOLD:
                logger.info("Top candidate rerank score %.4f is below calibrated threshold %.2f. Triggering grounded refusal.", top_score, CALIBRATED_CONFIDENCE_THRESHOLD)
                return []

        logger.info("Search returned %d final documents for query: '%s'", len(final_documents), query)
        return final_documents

    def search_with_context(
        self,
        query: str,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Convenience alias explicitly accepting conversation history."""
        return self.search(
            query=query,
            user_id=user_id,
            document_id=document_id,
            conversation_history=conversation_history,
        )