"""Simple Chroma wrapper for on-disk vector storage.

This module keeps the dependency on chromadb isolated. If chromadb is not
installed the import will fail when attempting to use the store; code that
depends on it should guard accordingly.
"""
from typing import List, Dict, Any, Optional
from modules.logger import get_logger
from modules.config_manager import get_embeddings_config


class VectorStore:
    def __init__(self, persist_directory: Optional[str] = None, collection_name: Optional[str] = None):
        try:
            import chromadb
        except Exception as e:
            raise ImportError("chromadb is required for the vector store") from e

        config = get_embeddings_config()
        persist_directory = persist_directory or config["persist_directory"]
        self._default_collection_name = collection_name or config["collection_name"]

        # chromadb>=0.4.0 replaced Settings(chroma_db_impl=...) with
        # PersistentClient(path=...) as the supported persistence API.
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = None

    def ensure_collection(self, name: Optional[str] = None):
        name = name or self._default_collection_name
        if self.collection:
            return self.collection
        self.collection = self.client.get_or_create_collection(name)
        return self.collection

    def upsert_docs(self, ids: List[str], texts: List[str], embeddings: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None):
        col = self.ensure_collection()
        # chromadb>=1.0 rejects empty metadata dicts, so fall back to a
        # non-empty placeholder instead of {}.
        col.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas or [{"source": "unknown"}] * len(ids))

    def query(self, query_embedding: List[float], top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        col = self.ensure_collection()
        kwargs: Dict[str, Any] = {"query_embeddings": [query_embedding], "n_results": top_k}
        if where is not None:
            kwargs["where"] = where
        res = col.query(**kwargs)
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

    def search_keywords(self, keywords: List[str], top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Lexical keyword search over stored documents (best-effort fallback).

        Scores each document by how many keywords appear (case-insensitive
        substring match) and returns the top hits in the same dict shape as
        `query`, with distance None — keyword hits are lexical, not vector.
        An optional chroma `where` filter narrows the scanned documents.
        Returns [] on any error.
        """
        col = self.ensure_collection()
        try:
            kwargs: Dict[str, Any] = {"include": ["documents", "metadatas"]}
            if where is not None:
                kwargs["where"] = where
            res = col.get(**kwargs)
        except Exception:
            return []
        ids = res.get("ids", []) or []
        docs = res.get("documents", []) or []
        metas = res.get("metadatas", []) or []
        kws = [k.lower() for k in keywords if k]
        if not kws:
            return []
        scored = []
        for i, doc in enumerate(docs):
            if doc is None:
                continue
            text = str(doc).lower()
            score = sum(1 for k in kws if k in text)
            if score:
                scored.append((score, {
                    "id": ids[i] if i < len(ids) else None,
                    "document": doc,
                    "metadata": metas[i] if i < len(metas) else None,
                    "distance": None,
                }))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]
