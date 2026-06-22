import json
import os
from typing import Dict, List

HERE = os.path.dirname(__file__)
_CATS_PATH = os.path.join(HERE, "question_categories.json")

try:
    with open(_CATS_PATH, "r", encoding="utf-8") as f:
        _CATEGORIES = json.load(f)
except Exception:
    _CATEGORIES = {}


def _count_keyword_matches(text: str, keywords: List[str]) -> int:
    cnt = 0
    for kw in keywords:
        if kw in text:
            cnt += 1
    return cnt


def classify_question(question: str) -> Dict:
    q = (question or "").lower()

    # Rule-based matching
    scores = {}
    for cid, meta in _CATEGORIES.items():
        kws = meta.get("keywords", [])
        scores[cid] = _count_keyword_matches(q, kws)

    # Find top two
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_id, top_score = (sorted_scores[0] if sorted_scores else (None, 0))
    next_score = (sorted_scores[1][1] if len(sorted_scores) > 1 else 0)

    if top_score > 0 and top_score >= 2 * next_score:
        confidence = min(0.9, 0.5 + 0.1 * top_score)
        return {
            "category_id": top_id,
            "category_label": _CATEGORIES.get(top_id, {}).get("label", top_id),
            "method": "rule",
            "confidence": float(confidence),
            "matched_keywords": [k for k in _CATEGORIES.get(top_id, {}).get("keywords", []) if k in q],
        }

    # Fallback to embedding-based if available
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer('all-MiniLM-L6-v2')
        q_emb = model.encode([question])[0]

        # compute embeddings for category descriptions
        descs = [meta.get('description', '') for meta in _CATEGORIES.values()]
        ids = list(_CATEGORIES.keys())
        if descs:
            desc_embs = model.encode(descs)
            # cosine similarities
            sims = np.dot(desc_embs, q_emb) / (np.linalg.norm(desc_embs, axis=1) * (np.linalg.norm(q_emb) + 1e-12))
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])
            if best_sim > 0.6:
                cid = ids[best_idx]
                return {
                    "category_id": cid,
                    "category_label": _CATEGORIES.get(cid, {}).get("label", cid),
                    "method": "embed",
                    "confidence": best_sim,
                    "matched_keywords": [],
                }
    except Exception:
        # sentence-transformers not available or failed — ignore
        pass

    return {"category_id": "general", "category_label": "general", "method": "none", "confidence": 0.0, "matched_keywords": []}


if __name__ == "__main__":
    print(classify_question("How do I manage wave and cs in early lane?"))
