import sys
import types
import pytest


def test_vectorstore_requires_chromadb(monkeypatch):
    # Ensure ImportError is raised when chromadb is not available
    monkeypatch.setitem(sys.modules, 'chromadb', None)
    from importlib import reload

    with pytest.raises(ImportError):
        # reload the module to trigger import
        import importlib
        import modules.embeddings.store as store_mod
        reload(store_mod)
        store_mod.VectorStore()
