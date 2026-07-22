"""
Trip Swarm — rag_backend.py

Agentic RAG completely SEPARATE from travel agents.
Architecture:
  1. route_query   → LLM decides: hybrid vector search OR direct LLM answer
  2. hybrid_search → Dense (ChromaDB embeddings) + Sparse (BM25) → RRF re-rank
  3. rag_generate  → Answer from retrieved context + conversational memory
  4. llm_direct    → Answer directly with conversational memory

User isolation: every chunk is tagged with user_id in Chroma metadata.
Queries always filter by user_id so users NEVER see each other's data.
"""

import os
import io
import uuid
from typing import TypedDict, Optional, List, Dict, Any

import numpy as np
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.graph import StateGraph, END
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi

from langchain_community.embeddings import FastEmbedEmbeddings

load_dotenv()

# ChromaDB Setup

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = "tripswarm_user_docs"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Sentence-transformers for local embeddings
embeddings_model = FastEmbedEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)

# Persistent ChromaDB client
chroma_client = chromadb.PersistentClient(
    path=CHROMA_PERSIST_DIR,
    settings=Settings(anonymized_telemetry=False),
)

# LLM for routing and generation
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="openai/gpt-oss-120b",
    temperature=0.25,
    max_tokens=768,
)


def get_collection() -> chromadb.Collection:
    """Get or create the Chroma collection for user documents."""
    return chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# Document Processing

def extract_text_from_file(content: bytes, filename: str, content_type: str) -> str:
    """Extract plain text from PDF, DOCX, or text files."""
    name = (filename or "").lower()
    ct = (content_type or "").lower()

    # PDF
    if name.endswith(".pdf") or "pdf" in ct:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            texts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
            return "\n\n".join(texts)
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return ""

    # DOCX
    if name.endswith(".docx") or "word" in ct or "openxmlformats" in ct:
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            return ""

    # Plain text / Markdown
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


async def add_document_to_chroma(
    file_content: bytes,
    filename: str,
    content_type: str,
    user_id: str,
) -> str:
    """
    Process a user-uploaded document and add it to ChromaDB.
    Every chunk is tagged with user_id for strict user isolation.
    Returns the doc_id (UUID) for DB reference.
    """
    text = extract_text_from_file(file_content, filename, content_type)

    if not text.strip():
        print(f"Warning: No text extracted from {filename}")
        return str(uuid.uuid4())

    # Split into overlapping chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
        keep_separator=False,
    )
    chunks = splitter.split_text(text)

    if not chunks:
        return str(uuid.uuid4())

    # Generate embeddings
    chunk_embeddings = embeddings_model.embed_documents(chunks)

    # Unique doc_id — stored as metadata in every chunk
    doc_id = str(uuid.uuid4())
    collection = get_collection()

    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "user_id": user_id,      # KEY: user isolation
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        for i in range(len(chunks))
    ]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=chunk_embeddings,
        metadatas=metadatas,
    )

    print(f"Added {len(chunks)} chunks for {filename} (user={user_id}, doc_id={doc_id})")
    return doc_id


async def delete_document(chroma_doc_id: str, user_id: str) -> None:
    """Delete all chunks of a document from ChromaDB (user-scoped)."""
    collection = get_collection()
    try:
        results = collection.get(
            where={"$and": [
                {"user_id": {"$eq": user_id}},
                {"doc_id": {"$eq": chroma_doc_id}},
            ]}
        )
        if results["ids"]:
            collection.delete(ids=results["ids"])
            print(f"Deleted {len(results['ids'])} chunks for doc_id={chroma_doc_id}")
    except Exception as e:
        print(f"Error deleting document: {e}")


# Hybrid Search (Dense + Sparse + RRF)

def hybrid_search(query: str, user_id: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Hybrid search combining:
      - Dense: ChromaDB cosine similarity (semantic)
      - Sparse: BM25 keyword matching over retrieved docs
      - Re-rank: Reciprocal Rank Fusion (RRF)

    All results are user-scoped via Chroma metadata filter.
    """
    collection = get_collection()

    # Quick check: does this user have any documents?
    try:
        probe = collection.get(where={"user_id": {"$eq": user_id}}, limit=1)
        if not probe["ids"]:
            return []  # No user documents, skip RAG
    except Exception:
        return []

    # Step 1: Dense search via Chroma

    query_embedding = embeddings_model.embed_query(query)
    candidate_count = min(n_results * 4, 30)

    try:
        dense_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_count,
            where={"user_id": {"$eq": user_id}},
            include=["documents", "metadatas", "distances"],  # ← remove "ids"
        )
    except Exception as e:
        print(f"Dense search error: {e}")
        return []

    docs_list = dense_results.get("documents", [[]])[0]
    meta_list = dense_results.get("metadatas", [[]])[0]
    ids_list  = dense_results.get("ids", [[]])[0]
    dist_list = dense_results.get("distances", [[]])[0]

    if not docs_list:
        return []

    # Step 2: BM25 sparse search over the retrieved candidates

    tokenized_corpus = [doc.lower().split() for doc in docs_list]
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = query.lower().split()
    bm25_scores = bm25.get_scores(tokenized_query)

    #  Step 3: Reciprocal Rank Fusion 

    K = 60  # RRF constant

    # Dense ranks (already sorted by distance, lower = better)
    dense_ranks = {chunk_id: rank + 1 for rank, chunk_id in enumerate(ids_list)}

    # Sparse ranks (sort by BM25 score, higher = better)
    bm25_order = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
    sparse_ranks = {ids_list[i]: rank + 1 for rank, i in enumerate(bm25_order)}

    # RRF score
    rrf_scores: Dict[str, float] = {}
    for chunk_id in ids_list:
        rrf_scores[chunk_id] = (
            1.0 / (K + dense_ranks.get(chunk_id, 1000)) +
            1.0 / (K + sparse_ranks.get(chunk_id, 1000))
        )

    # Sort by RRF and take top n_results
    top_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:n_results]

    # Build result list
    id_to_data = {
        chunk_id: {"content": doc, "metadata": meta, "distance": dist}
        for chunk_id, doc, meta, dist in zip(ids_list, docs_list, meta_list, dist_list)
    }

    results = []
    for chunk_id in top_ids:
        if chunk_id in id_to_data:
            d = id_to_data[chunk_id]
            results.append({
                "content":  d["content"],
                "metadata": d["metadata"],
                "score":    rrf_scores[chunk_id],
                "distance": d["distance"],
            })

    return results


# Agentic RAG State

class RAGState(TypedDict):
    query:          str
    user_id:        str
    chat_history:   List[Dict[str, str]]   # conversational memory
    route:          Optional[str]          # "rag" | "llm"
    retrieved_docs: List[Dict[str, Any]]
    answer:         str
    source:         str                    # "rag" | "llm"


# Node 1: Route query

def route_query_node(state: RAGState) -> RAGState:
    collection = get_collection()
    try:
        probe = collection.get(where={"user_id": {"$eq": state["user_id"]}}, limit=1)
        has_docs = len(probe["ids"]) > 0
    except Exception:
        has_docs = False

    if not has_docs:
        return {**state, "route": "llm"}

    router_prompt = """You are a query router. Reply with ONLY the word "rag" or "llm".

rag → the question references personal documents, bookings, tickets, reservations,
      itineraries, "my", "uploaded", "this file", "the document", etc.
llm → general travel knowledge, destinations, tips, weather, visa rules, packing, etc.

Reply with exactly one word: rag or llm"""

    try:
        response = llm.invoke([
            SystemMessage(content=router_prompt),
            HumanMessage(content=state["query"]),
        ])
        route = response.content.strip().lower().split()[0]  # take FIRST word only
        route = route if route in ("rag", "llm") else "llm"
    except Exception as e:
        print(f"Router error: {e}")
        route = "llm"

    return {**state, "route": route}

# Node 2: Hybrid search 

def hybrid_search_node(state: RAGState) -> RAGState:
    """Retrieve relevant document chunks using hybrid dense+sparse search."""
    docs = hybrid_search(
        query=state["query"],
        user_id=state["user_id"],
        n_results=5,
    )
    return {**state, "retrieved_docs": docs}


def decide_after_search(state: RAGState) -> str:
    """
    Decide what to do after hybrid retrieval.

    Returns:
        rag -> Retrieved documents found.
        llm -> No relevant documents found.
    """
    docs = state.get("retrieved_docs", [])

    if docs:
        return "rag"

    return "llm"


# Node 3: RAG generate

def rag_generate_node(state: RAGState) -> RAGState:
    """
    Generate answer using:
    - Retrieved context from user's documents
    - Conversational memory (last N exchanges from thread)
    """
    docs = state["retrieved_docs"]

    context_parts = []

    for doc in docs:
        fname = doc["metadata"].get("filename", "your document")
        context_parts.append(
            f"[Source: {fname}]\n{doc['content']}"
        )

    context = "\n\n---\n\n".join(context_parts)
    source = "rag"

    system_msg = f"""You are Trip Swarm's travel assistant.
    Answer using the user's uploaded documents below. Be concise — 2–4 sentences max unless the user asks for detail.
    If the context doesn't cover the question, say so briefly and supplement with general knowledge.

    Documents:
    {context}"""

    messages: list = [SystemMessage(content=system_msg)]

    # Add conversational memory (last 8 messages = 4 turns)
    for msg in state["chat_history"][-8:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=state["query"]))

    try:
        resp = llm.invoke(messages)
        answer = resp.content
    except Exception as e:
        answer = f"I encountered an error generating a response. Please try again. ({e})"

    return {**state, "answer": answer, "source": source}


#  Node 4: Direct LLM answer

def llm_direct_node(state: RAGState) -> RAGState:
    """Answer directly from LLM general knowledge with conversational memory."""
    system_msg = """You are Trip Swarm's travel assistant.
    Give concise, practical answers — 2–4 sentences max unless detail is requested.
    For real-time info (prices, availability, live visa rules), tell the user to check official sources."""

    messages: list = [SystemMessage(content=system_msg)]

    # Conversational memory
    for msg in state["chat_history"][-8:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=state["query"]))

    try:
        resp = llm.invoke(messages)
        answer = resp.content
    except Exception as e:
        answer = f"I encountered an error. Please try again. ({e})"

    return {**state, "answer": answer, "source": "llm"}


#  Conditional edge: route decision
def decide_route(state: RAGState) -> str:
    return state.get("route", "llm")


# Build LangGraph 

rag_graph = StateGraph(RAGState)

rag_graph.add_node("route_query",    route_query_node)
rag_graph.add_node("hybrid_search",  hybrid_search_node)
rag_graph.add_node("rag_generate",   rag_generate_node)
rag_graph.add_node("llm_direct",     llm_direct_node)

rag_graph.set_entry_point("route_query")

rag_graph.add_conditional_edges(
    "route_query",
    decide_route,
    {
        "rag": "hybrid_search",
        "llm": "llm_direct",
    },
)

rag_graph.add_conditional_edges(
    "hybrid_search",
    decide_after_search,
    {
        "rag": "rag_generate",
        "llm": "llm_direct",
    },
)

rag_graph.add_edge("rag_generate", END)
rag_graph.add_edge("llm_direct",   END)

rag_app = rag_graph.compile()


# Public API

async def run_rag_workflow(
    query: str,
    user_id: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Run the agentic RAG workflow.
    Returns: { answer, source, documents_used }
    """
    initial_state = RAGState(
        query=query,
        user_id=user_id,
        chat_history=chat_history or [],
        route=None,
        retrieved_docs=[],
        answer="",
        source="",
    )

    result = await rag_app.ainvoke(initial_state)

    return {
        "answer": result["answer"],
        "source": result["source"],
        "documents_used": [
            {
                "filename": d["metadata"].get("filename", "unknown"),
                "score": round(d["score"], 4),
            }
            for d in result.get("retrieved_docs", [])
        ],
    }
