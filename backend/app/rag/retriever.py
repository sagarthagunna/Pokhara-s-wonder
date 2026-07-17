"""
app/rag/retriever.py

Thin wrapper around the ChromaDB collection built by ingest.py.
This is what look_up_artifact() (in app/tools/) calls under the hood.

The key line is `where={"location": location}` — this is the metadata
filter. Without it, a query made while standing at Devi's Fall could
retrieve chunks about the Deep Cave Shivalaya, which breaks the
"RAG Boundaries" requirement from the spec (each location should only
surface its own facts).
"""

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.rag.ingest import COLLECTION_NAME

_client = None
_collection = None


def _get_collection():
    """Lazy singleton — avoids reloading the embedding model on every call."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL
        )
        _collection = _client.get_collection(
            name=COLLECTION_NAME, embedding_function=embed_fn
        )
    return _collection


def query_location(location: str, query: str, n_results: int = 3) -> list[dict]:
    """
    Metadata-filtered semantic search.

    Returns a list of {"text": ..., "source_file": ...} dicts, restricted
    to chunks tagged with the given location.
    """
    collection = _get_collection()

    result = collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"location": location},
    )

    hits = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        hits.append({"text": doc, "source_file": meta.get("source_file")})
    return hits
