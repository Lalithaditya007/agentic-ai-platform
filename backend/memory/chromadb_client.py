import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from config import settings

_client = None

# Collections used across the platform
COLLECTION_COMPANY_KNOWLEDGE = "company_knowledge"
COLLECTION_BUSINESS_CONTEXT = "business_context"
COLLECTION_HISTORICAL_DECISIONS = "historical_decisions"
COLLECTION_BUSINESS_BRIEFS = "business_briefs_store"

# ChromaDB 1.x built-in default embedding function (uses onnxruntime — no sentence-transformers needed)
_embedding_fn = DefaultEmbeddingFunction()


def init_chromadb():
    """Initialize ChromaDB in embedded (in-process) mode."""
    global _client
    _client = chromadb.PersistentClient(path=settings.CHROMADB_PERSIST_PATH)

    # Ensure all required collections exist
    for collection_name in [
        COLLECTION_COMPANY_KNOWLEDGE,
        COLLECTION_BUSINESS_CONTEXT,
        COLLECTION_HISTORICAL_DECISIONS,
        COLLECTION_BUSINESS_BRIEFS,
    ]:
        _client.get_or_create_collection(
            name=collection_name,
            embedding_function=_embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    print(f"[OK] ChromaDB initialized with {len([COLLECTION_COMPANY_KNOWLEDGE, COLLECTION_BUSINESS_CONTEXT, COLLECTION_HISTORICAL_DECISIONS, COLLECTION_BUSINESS_BRIEFS])} collections")


def get_chromadb() -> chromadb.PersistentClient:
    """Get the ChromaDB client."""
    if _client is None:
        raise RuntimeError("ChromaDB not initialized. Call init_chromadb() first.")
    return _client


def get_collection(name: str) -> chromadb.Collection:
    return get_chromadb().get_collection(name=name, embedding_function=_embedding_fn)


# ── Helper methods ────────────────────────────────────────

def chroma_add(collection_name: str, documents: list[str], ids: list[str], metadatas: list[dict] = None):
    col = get_collection(collection_name)
    col.add(documents=documents, ids=ids, metadatas=metadatas or [{}] * len(documents))


def chroma_query(collection_name: str, query_text: str, n_results: int = 5) -> list[dict]:
    col = get_collection(collection_name)
    results = col.query(query_texts=[query_text], n_results=n_results)
    if not results["ids"] or not results["ids"][0]:
        return []
    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        output.append({
            "id": doc_id,
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "distance": results["distances"][0][i] if results["distances"] else 1.0,
        })
    return output


def chroma_upsert(collection_name: str, documents: list[str], ids: list[str], metadatas: list[dict] = None):
    col = get_collection(collection_name)
    col.upsert(documents=documents, ids=ids, metadatas=metadatas or [{}] * len(documents))
