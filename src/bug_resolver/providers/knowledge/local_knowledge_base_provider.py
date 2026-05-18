from pathlib import Path

from bug_resolver.providers.knowledge.base import KnowledgeBaseProvider
from bug_resolver.schemas.knowledge_context import KnowledgeContext


SUPPORTED_DOC_EXTENSIONS = {".md", ".txt"}


class LocalKnowledgeBaseProvider(KnowledgeBaseProvider):
    def __init__(self, knowledge_base_dir: str | Path, max_results: int = 5) -> None:
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.max_results = max_results

    def search_docs(self, queries: list[str]) -> list[KnowledgeContext]:
        if not queries:
            return []

        documents = self._load_documents()
        scored_documents = self._score_documents(documents=documents, queries=queries)

        top_documents = sorted(
            scored_documents,
            key=lambda item: item[1],
            reverse=True,
        )[: self.max_results]

        return [
            self._to_knowledge_context(
                file_path=file_path,
                content=content,
                score=score,
                retrieval_query=matched_query,
            )
            for file_path, score, content, matched_query in top_documents
            if score > 0
        ]

    def _load_documents(self) -> list[tuple[Path, str]]:
        if not self.knowledge_base_dir.exists():
            return []

        documents: list[tuple[Path, str]] = []

        for file_path in self.knowledge_base_dir.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in SUPPORTED_DOC_EXTENSIONS:
                continue

            content = file_path.read_text(encoding="utf-8")
            documents.append((file_path, content))

        return documents

    def _score_documents(
        self,
        documents: list[tuple[Path, str]],
        queries: list[str],
    ) -> list[tuple[Path, float, str, str | None]]:
        scored_documents: list[tuple[Path, float, str, str | None]] = []

        normalized_queries = [query.lower() for query in queries]

        for file_path, content in documents:
            normalized_content = content.lower()
            score, matched_query = self._score_content(
                normalized_content=normalized_content,
                normalized_queries=normalized_queries,
            )

            scored_documents.append((file_path, score, content, matched_query))

        return scored_documents

    def _score_content(
        self,
        normalized_content: str,
        normalized_queries: list[str],
    ) -> tuple[float, str | None]:
        score = 0.0
        best_query: str | None = None

        for query in normalized_queries:
            query_score = 0.0
            query_terms = self._split_query(query)

            for term in query_terms:
                if term in normalized_content:
                    query_score += 1.0

            if query in normalized_content:
                query_score += 3.0

            if query_score > 0 and query_score > score:
                best_query = query

            score += query_score

        return score, best_query

    def _split_query(self, query: str) -> list[str]:
        return [
            term.strip()
            for term in query.lower().split()
            if term.strip()
        ]

    def _to_knowledge_context(
        self,
        file_path: Path,
        content: str,
        score: float,
        retrieval_query: str | None,
    ) -> KnowledgeContext:
        return KnowledgeContext(
            context_id=f"kb-{file_path.stem}",
            document_name=file_path.name,
            content=content,
            section_title=None,
            file_path=str(file_path),
            retrieval_query=retrieval_query,
            relevance_score=min(score / 10, 1.0),
            metadata={
                "provider": "local_knowledge_base",
            },
        )