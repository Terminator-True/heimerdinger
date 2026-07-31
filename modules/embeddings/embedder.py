"""Embedding wrapper using sentence-transformers.

Provides a lightweight adapter so the rest of the codebase can request
embeddings without coupling to the library directly. Falls back gracefully
when sentence-transformers is not installed (raises ImportError at runtime
when used).
"""
from typing import List


class Embedder:
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise ImportError("sentence-transformers is required for local embeddings") from e

        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return list of vector embeddings for the given texts.

        Args:
            texts: list of strings to embed
        Returns:
            List of vectors (list of floats)
        """
        if not texts:
            return []
        vectors = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        # ensure JSON-serializable nested lists
        return [list(map(float, v.tolist() if hasattr(v, 'tolist') else v)) for v in vectors]
