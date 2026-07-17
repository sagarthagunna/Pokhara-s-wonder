"""
app/rag/ingest.py

Reads the .txt knowledge files in app/rag/knowledge/, splits each into
paragraph-sized chunks, and loads them into a persistent ChromaDB
collection — tagging every chunk with a `location` metadata field.

This metadata tag is what makes this "metadata-filtered RAG": when the
agent is in devis_fall, we query Chroma with `where={"location": "devis_fall"}`
so the retriever can ONLY see chunks from that location's document, even
though all three locations' knowledge lives in the same collection.

Run manually to (re)build the index:
    python -m app.rag.ingest
"""

import pathlib
import chromadb
from chromadb.utils import embedding_functions

from app.config import settings

KNOWLEDGE_DIR = pathlib.Path(__file__).parent / "knowledge"
COLLECTION_NAME = "cave_explorer_kb"

# filename (without .txt) -> location id used throughout the app
LOCATION_FILES = {
    "devis_fall": "devis_fall.txt",
    "entrance_plaza": "entrance_plaza.txt",
    "deep_shivalaya": "deep_shivalaya.txt",
}


def chunk_text(text: str, min_len: int = 40) -> list[str]:
    """Split on blank lines (paragraphs / ## sections) into retrievable chunks."""
    raw_chunks = [c.strip() for c in text.split("\n\n")]
    return [c for c in raw_chunks if len(c) >= min_len]


def build_index():
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.EMBEDDING_MODEL
    )

    # Fresh rebuild each time this script runs, so re-running it is safe
    # after you edit the knowledge .txt files.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    ids, documents, metadatas = [], [], []

    for location, filename in LOCATION_FILES.items():
        filepath = KNOWLEDGE_DIR / filename
        text = filepath.read_text(encoding="utf-8")
        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            ids.append(f"{location}_{i}")
            documents.append(chunk)
            metadatas.append({"location": location, "source_file": filename})

        print(f"  {location}: {len(chunks)} chunks")

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Indexed {len(ids)} chunks total into '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    build_index()
