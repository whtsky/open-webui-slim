"""
ColBERT reranker stub for Open WebUI Slim.

The original ColBERT implementation requires torch and colbert-ai, which are
removed in the slim build. This stub preserves the module so existing imports
don't cause ImportError at the module level, but raises NotImplementedError
if anyone tries to instantiate the class.
"""

import logging

from open_webui.retrieval.models.base_reranker import BaseReranker

log = logging.getLogger(__name__)


class ColBERT(BaseReranker):
    def __init__(self, name, **kwargs) -> None:
        raise NotImplementedError(
            'ColBERT reranking is not available in the slim build. '
            'Use an external reranking engine instead (e.g., set '
            'RAG_RERANKING_ENGINE to "openai" or another API provider).'
        )

    def calculate_similarity_scores(self, query_embeddings, document_embeddings):
        raise NotImplementedError('ColBERT is not available in the slim build.')

    def predict(self, sentences):
        raise NotImplementedError('ColBERT is not available in the slim build.')
