"""Simple Chroma wrapper for on-disk vector storage.

This module keeps the dependency on chromadb isolated. If chromadb is not
installed the import will fail when attempting to use the store; code that
depends on it should guard accordingly.
"""
from typing import List, Dict, Any, Optional


class VectorStore:
    def __init__(self, persist_directory: str = "chromadb_store"):
        try:
            import chromadb
            from chromadb.config import Settings
        except Exception as e:
            raise ImportError("chromadb is required for the vector store") from e

        self.client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=persist_directory))
        self.collection = None

    def ensure_collection(self, name: str = "heimerdinger"):
        if self.collection:
            return self.collection
        # create or get existing
        try:
            self.collection = self.client.get_collection(name)
        except Exception:
            self.collection = self.client.create_collection(name)
        return self.collection

    def upsert_docs(self, ids: List[str], texts: List[str], embeddings: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None):
        col = self.ensure_collection()
        col.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas or [{}] * len(ids))

    def query(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        col = self.ensure_collection()
        res = col.query(query_embeddings=[query_embedding], n_results=top_k)
        # result fields: ids, distances, documents, metadatas
        out = []
        for idx, doc in enumerate(res.get("documents", [[]])[0]):
            out.append({
                "id": res.get("ids", [[]])[0][idx],
                "document": doc,
                "metadata": res.get("metadatas", [[]])[0][idx],
                "distance": res.get("distances", [[]])[0][idx],
            })
        return out
