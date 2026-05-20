# Reranking Configuration

Hybrid retrieval should rerank candidate chunks before answer generation.

`RERANKING_MODEL_NAME` must identify a supported cross-encoder model. If the
reranker model is missing or cannot load, the application should warn clearly
and fail over through an explicit policy.

Silent reranker bypass is not acceptable for production retrieval quality
because the original vector or keyword order may not put the most answerable
chunk first.
