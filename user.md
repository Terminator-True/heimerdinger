Ask Coach changes

- The ask_coach flow now uses a hybrid question classification + retrieval system.

- Categories available (modules/llm/question_categories.json): laning, vision, macro, teamfights, pacing, mental.

- Behavior: the question is classified using a rule-based keyword scan first. If the rule-based scan is inconclusive, the system will attempt an embedding-based classification (if sentence-transformers is installed). If both fail, the question is categorized as 'general'.

- Retrieval: recipes in modules/llm/retrieval.py will attempt to pull compact passages from the reports collection tailored to the detected category. If this yields nothing, the previous embedding vector-store retrieval is used as a fallback.

- The prompt built for the LLM includes the retrieved passages to provide focused coaching advice.
