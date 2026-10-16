"""
Evaluation dataset for Advanced RAG v2 benchmark suite.
Covers Categories A through J with structured expectations:
- Category A: Definitions
- Category B: Explanations
- Category C: Code / Example Intent
- Category D: Specific Factual Retrieval
- Category E: Multi-Concept
- Category F: Multi-Document
- Category G: Follow-Up Questions (Conversational sequences)
- Category H: Out-of-Domain (Grounded Refusal)
- Category I: Adversarial / Ambiguous
- Category J: Long Answers
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TestCase:
    id: str
    category: str
    query: str
    expected_intent: str
    expected_concepts: List[str]
    expected_code: bool = False
    is_out_of_domain: bool = False
    expected_refusal: bool = False
    conversation_history: Optional[List[Dict[str, str]]] = None
    expected_sources: Optional[List[str]] = None
    description: str = ""


EVALUATION_DATASET: List[TestCase] = [
    # ============================================================
    # CATEGORY A — DEFINITIONS
    # ============================================================
    TestCase(
        id="A1",
        category="Category A - Definitions",
        query="What is OOPS?",
        expected_intent="definition",
        expected_concepts=["object oriented programming", "objects", "classes"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Core definition of Object Oriented Programming"
    ),
    TestCase(
        id="A2",
        category="Category A - Definitions",
        query="What is abstraction?",
        expected_intent="definition",
        expected_concepts=["abstraction", "essential features", "background details"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Definition of data abstraction"
    ),
    TestCase(
        id="A3",
        category="Category A - Definitions",
        query="What is inheritance?",
        expected_intent="definition",
        expected_concepts=["inheritance", "properties", "reusability", "derived"],
        expected_sources=["285_OOPS lecture notes Complete.pdf", "PYTHON PROGRAMMING NOTES.docx"],
        description="Definition of inheritance"
    ),
    TestCase(
        id="A4",
        category="Category A - Definitions",
        query="What is encapsulation?",
        expected_intent="definition",
        expected_concepts=["encapsulation", "wrapping", "data", "functions"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Definition of data encapsulation"
    ),
    TestCase(
        id="A5",
        category="Category A - Definitions",
        query="What is polymorphism?",
        expected_intent="definition",
        expected_concepts=["polymorphism", "multiple forms", "overloading", "virtual"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Definition of polymorphism"
    ),
    TestCase(
        id="A6",
        category="Category A - Definitions",
        query="What is a process?",
        expected_intent="definition",
        expected_concepts=["process", "program in execution", "operating system"],
        expected_sources=["Operating-System (1).csv"],
        description="Definition of operating system process"
    ),
    TestCase(
        id="A7",
        category="Category A - Definitions",
        query="What is TCP?",
        expected_intent="definition",
        expected_concepts=["tcp", "transmission control protocol", "connection", "reliable"],
        expected_sources=["COMPUTER NETWORKS NOTES.txt"],
        description="Definition of TCP protocol"
    ),

    # ============================================================
    # CATEGORY B — EXPLANATIONS
    # ============================================================
    TestCase(
        id="B1",
        category="Category B - Explanations",
        query="Explain abstraction in detail.",
        expected_intent="explanation",
        expected_concepts=["abstraction", "essential features", "class", "pure virtual"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="In-depth conceptual explanation of abstraction"
    ),
    TestCase(
        id="B2",
        category="Category B - Explanations",
        query="Explain inheritance in Python.",
        expected_intent="explanation",
        expected_concepts=["inheritance", "python", "base class", "derived class"],
        expected_sources=["PYTHON PROGRAMMING NOTES.docx"],
        description="Explanation of Python inheritance"
    ),
    TestCase(
        id="B3",
        category="Category B - Explanations",
        query="Explain operating system functions.",
        expected_intent="explanation",
        expected_concepts=["operating system", "process management", "memory", "resource"],
        expected_sources=["Operating-System (1).csv"],
        description="Explanation of operating system core functions"
    ),
    TestCase(
        id="B4",
        category="Category B - Explanations",
        query="Explain TCP three-way handshake.",
        expected_intent="explanation",
        expected_concepts=["tcp", "three-way handshake", "syn", "ack"],
        expected_sources=["COMPUTER NETWORKS NOTES.txt"],
        description="Explanation of TCP connection establishment"
    ),

    # ============================================================
    # CATEGORY C — CODE / EXAMPLE INTENT
    # ============================================================
    TestCase(
        id="C1",
        category="Category C - Code/Example",
        query="Give me the example code of abstraction.",
        expected_intent="code_example",
        expected_concepts=["abstraction", "abstract class", "pure virtual"],
        expected_code=True,
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Code example demonstrating abstraction with abstract class or pure virtual function"
    ),
    TestCase(
        id="C2",
        category="Category C - Code/Example",
        query="Show me the Payment abstraction example.",
        expected_intent="code_example",
        expected_concepts=["abstraction", "abstract class", "pure virtual"],
        expected_code=True,
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Abstraction code example; distinguishes general abstraction evidence from absent payment-specific content"
    ),
    TestCase(
        id="C3",
        category="Category C - Code/Example",
        query="Explain abstraction with code.",
        expected_intent="code_example",
        expected_concepts=["abstraction", "class", "virtual"],
        expected_code=True,
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Explanation of abstraction combined with grounded code snippet"
    ),
    TestCase(
        id="C4",
        category="Category C - Code/Example",
        query="Give me an example of inheritance.",
        expected_intent="code_example",
        expected_concepts=["inheritance", "base", "derived"],
        expected_code=True,
        expected_sources=["285_OOPS lecture notes Complete.pdf", "PYTHON PROGRAMMING NOTES.docx"],
        description="Code example demonstrating class inheritance"
    ),
    TestCase(
        id="C5",
        category="Category C - Code/Example",
        query="Show me a pure virtual function example.",
        expected_intent="code_example",
        expected_concepts=["pure virtual", "virtual", "= 0"],
        expected_code=True,
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Code example for pure virtual function syntax"
    ),

    # ============================================================
    # CATEGORY D — SPECIFIC FACTUAL RETRIEVAL
    # ============================================================
    TestCase(
        id="D1",
        category="Category D - Specific Factual",
        query="What are the characteristics of an abstract class in C++?",
        expected_intent="factual",
        expected_concepts=["abstract class", "pure virtual", "cannot be instantiated"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Specific factual properties of abstract classes"
    ),
    TestCase(
        id="D2",
        category="Category D - Specific Factual",
        query="What is the function of the transport layer in computer networks?",
        expected_intent="factual",
        expected_concepts=["transport layer", "end-to-end", "tcp", "udp"],
        expected_sources=["COMPUTER NETWORKS NOTES.txt"],
        description="Factual responsibility of transport layer"
    ),

    # ============================================================
    # CATEGORY E — MULTI-CONCEPT
    # ============================================================
    TestCase(
        id="E1",
        category="Category E - Multi-Concept",
        query="Explain abstraction and polymorphism and how they differ.",
        expected_intent="comparison",
        expected_concepts=["abstraction", "polymorphism", "differ"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Comparison between data abstraction and polymorphism"
    ),
    TestCase(
        id="E2",
        category="Category E - Multi-Concept",
        query="Compare inheritance and encapsulation.",
        expected_intent="comparison",
        expected_concepts=["inheritance", "encapsulation", "wrapping", "reusability"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Comparison between inheritance and encapsulation"
    ),
    TestCase(
        id="E3",
        category="Category E - Multi-Concept",
        query="Explain process vs thread in operating systems.",
        expected_intent="comparison",
        expected_concepts=["process", "thread", "operating system"],
        expected_sources=["Operating-System (1).csv"],
        description="Comparison between OS process and thread"
    ),

    # ============================================================
    # CATEGORY F — MULTI-DOCUMENT
    # ============================================================
    TestCase(
        id="F1",
        category="Category F - Multi-Document",
        query="How is inheritance explained in C++ vs Python across the documents?",
        expected_intent="comparison",
        expected_concepts=["inheritance", "c++", "python"],
        expected_sources=["285_OOPS lecture notes Complete.pdf", "PYTHON PROGRAMMING NOTES.docx"],
        description="Multi-document comparison across C++ and Python notes"
    ),

    # ============================================================
    # CATEGORY G — FOLLOW-UP QUESTIONS (CONVERSATION-AWARE)
    # ============================================================
    TestCase(
        id="G1",
        category="Category G - Follow-Up",
        query="Give me an example.",
        expected_intent="code_example",
        expected_concepts=["abstraction", "example"],
        expected_code=True,
        conversation_history=[
            {"role": "user", "content": "What is abstraction?"},
            {"role": "assistant", "content": "Abstraction refers to the act of representing essential features without including background details."}
        ],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Follow-up asking for example after asking about abstraction"
    ),
    TestCase(
        id="G2",
        category="Category G - Follow-Up",
        query="How does this relate to encapsulation?",
        expected_intent="comparison",
        expected_concepts=["abstraction", "encapsulation"],
        conversation_history=[
            {"role": "user", "content": "What is abstraction?"},
            {"role": "assistant", "content": "Abstraction represents essential features without background details."},
            {"role": "user", "content": "Give me an example."},
            {"role": "assistant", "content": "Here is an abstract class Base with pure virtual function virtual void show() = 0;"}
        ],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Follow-up comparing active topic (abstraction) to encapsulation"
    ),

    # ============================================================
    # CATEGORY H — OUT-OF-DOMAIN (STRICT REFUSAL)
    # ============================================================
    TestCase(
        id="H1",
        category="Category H - Out-of-Domain",
        query="What is the culinary history of chocolate in ancient Aztec civilization?",
        expected_intent="out_of_domain",
        expected_concepts=[],
        is_out_of_domain=True,
        expected_refusal=True,
        description="Unrelated query that must produce strict refusal with zero hallucination"
    ),
    TestCase(
        id="H2",
        category="Category H - Out-of-Domain",
        query="What is the authentic recipe for Hyderabadi biryani?",
        expected_intent="out_of_domain",
        expected_concepts=[],
        is_out_of_domain=True,
        expected_refusal=True,
        description="Unrelated culinary query that must produce strict refusal"
    ),
    TestCase(
        id="H3",
        category="Category H - Out-of-Domain",
        query="What were the causes of the fall of the Western Roman Empire?",
        expected_intent="out_of_domain",
        expected_concepts=[],
        is_out_of_domain=True,
        expected_refusal=True,
        description="Unrelated historical query that must produce strict refusal"
    ),

    # ============================================================
    # CATEGORY I — ADVERSARIAL / AMBIGUOUS
    # ============================================================
    TestCase(
        id="I1",
        category="Category I - Adversarial/Ambiguous",
        query="Tell me about it.",
        expected_intent="ambiguous",
        expected_concepts=[],
        conversation_history=None,
        expected_refusal=True,
        description="Ambiguous query with no prior conversational context"
    ),
    TestCase(
        id="I2",
        category="Category I - Adversarial/Ambiguous",
        query="What about the example?",
        expected_intent="ambiguous",
        expected_concepts=[],
        conversation_history=None,
        expected_refusal=True,
        description="Ambiguous query asking about an undefined example without context"
    ),

    # ============================================================
    # CATEGORY J — LONG ANSWERS
    # ============================================================
    TestCase(
        id="J1",
        category="Category J - Long Answer",
        query="Explain the basic concepts of object-oriented programming in detail with all features.",
        expected_intent="explanation",
        expected_concepts=["objects", "classes", "abstraction", "encapsulation", "inheritance", "polymorphism"],
        expected_sources=["285_OOPS lecture notes Complete.pdf"],
        description="Comprehensive long-form query requiring wide context retrieval"
    )
]
