"""
Embedding Service — Self-hosted embedding generation using multilingual-e5-large.

Responsibilities:
  - Generate 1024-dim embeddings for content chunks
  - Store embeddings in PostgreSQL + pgvector
  - Retrieve similar chunks via cosine similarity + metadata filtering
  - Hybrid search: semantic (pgvector) + keyword (pg_trgm)

Runs on CPU — no GPU needed for embedding generation.
"""

import logging
from typing import Sequence

import asyncpg
from pgvector.asyncpg import register_vector
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles embedding generation and vector search against pgvector.
    """

    def __init__(self):
        self.model: SentenceTransformer | None = None
        self.db_pool: asyncpg.Pool | None = None

    async def initialize(self):
        """Load the embedding model and connect to PostgreSQL."""
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        self.model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        logger.info(
            f"Embedding model loaded: dim={self.model.get_sentence_embedding_dimension()}, "
            f"device={settings.EMBEDDING_DEVICE}"
        )

        async def init_connection(conn):
            await register_vector(conn)

        self.db_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            init=init_connection,
        )
        logger.info("Database pool connected")

        # Ensure pgvector extension and table exist
        await self._ensure_schema()

    async def shutdown(self):
        """Cleanup resources."""
        if self.db_pool:
            await self.db_pool.close()

    async def _ensure_schema(self):
        """Create the embeddings table and indexes if they don't exist."""
        async with self.db_pool.acquire() as conn:
            # Register pgvector extension with asyncpg
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            
            # pgvector now usable in DDL
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {settings.VECTOR_TABLE} (
                    id              BIGSERIAL PRIMARY KEY,
                    chunk_id        TEXT UNIQUE NOT NULL,
                    source_id       TEXT NOT NULL,
                    source_type     TEXT NOT NULL,
                    language        TEXT NOT NULL DEFAULT 'en',
                    sensitivity     TEXT NOT NULL DEFAULT 'standard',
                    location_id     TEXT,
                    museum_id       TEXT,
                    route_id        TEXT,
                    tags            TEXT[] DEFAULT '{{}}',
                    text_content    TEXT NOT NULL,
                    embedding       vector({settings.EMBEDDING_DIMENSION}) NOT NULL,
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            # HNSW index for fast approximate nearest neighbor search
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
                ON {settings.VECTOR_TABLE}
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 200);
            """)

            # GIN index for keyword search via pg_trgm
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_embeddings_trgm
                ON {settings.VECTOR_TABLE}
                USING gin (text_content gin_trgm_ops);
            """)

            # B-tree indexes for metadata filtering
            for col in ["source_type", "language", "sensitivity", "location_id", "museum_id", "route_id"]:
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_{col}
                    ON {settings.VECTOR_TABLE} ({col});
                """)

            logger.info("Database schema verified")

    # ── Embedding Generation ─────────────────────────────

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        Uses the multilingual-e5-large model.

        For e5 models, prepend "passage: " for documents and "query: " for queries.
        """
        # e5 models expect prefixed inputs
        prefixed = [f"passage: {t}" for t in texts]
        embeddings = self.model.encode(
            prefixed,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=True,  # Normalize for cosine similarity
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a user query. Uses 'query: ' prefix for e5 models."""
        embedding = self.model.encode(
            f"query: {query}",
            normalize_embeddings=True,
        )
        return embedding.tolist()

    # ── Store Embeddings ─────────────────────────────────

    async def store_chunks(self, chunks: list[dict]) -> tuple[int, list[str]]:
        """
        Store content chunks with their embeddings in pgvector.

        Args:
            chunks: list of dicts with keys:
                chunk_id, text, source_id, source_type, language,
                sensitivity, location_id, museum_id, route_id, tags

        Returns:
            (success_count, error_messages)
        """
        texts = [c["text"] for c in chunks]
        embeddings = self.embed_texts(texts)

        success = 0
        errors = []

        async with self.db_pool.acquire() as conn:
            for chunk, embedding in zip(chunks, embeddings):
                try:
                    await conn.execute(f"""
                        INSERT INTO {settings.VECTOR_TABLE}
                            (chunk_id, source_id, source_type, language, sensitivity,
                             location_id, museum_id, route_id, tags, text_content, embedding)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            text_content = EXCLUDED.text_content,
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW()
                    """,
                        chunk["chunk_id"],
                        chunk["source_id"],
                        chunk["source_type"],
                        chunk.get("language", "en"),
                        chunk.get("sensitivity", "standard"),
                        chunk.get("location_id"),
                        chunk.get("museum_id"),
                        chunk.get("route_id"),
                        chunk.get("tags", []),
                        chunk["text"],
                        str(embedding),  # pgvector accepts string representation
                    )
                    success += 1
                except Exception as e:
                    errors.append(f"Chunk {chunk['chunk_id']}: {str(e)}")
                    logger.error(f"Failed to store chunk {chunk['chunk_id']}: {e}")

        logger.info(f"Stored {success}/{len(chunks)} chunks, {len(errors)} errors")
        return success, errors

    # ── Vector Search ────────────────────────────────────

    async def search(
        self,
        query: str,
        filters: dict | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Hybrid search: pgvector cosine similarity + optional keyword matching.

        Args:
            query: User's question text
            filters: Optional metadata filters:
                - source_type: str
                - language: str
                - sensitivity: str (max level to include)
                - location_id: str
                - museum_id: str
                - route_id: str
            limit: Max results to return

        Returns:
            List of matching chunks with similarity scores.
        """
        query_embedding = self.embed_query(query)
        limit = limit or settings.VECTOR_SEARCH_LIMIT

        # Build WHERE clause from filters
        where_clauses = []
        params = [str(query_embedding), limit]
        param_idx = 3  # $1=embedding, $2=limit

        if filters:
            if filters.get("source_type"):
                where_clauses.append(f"source_type = ${param_idx}")
                params.append(filters["source_type"])
                param_idx += 1

            if filters.get("language"):
                where_clauses.append(f"language = ${param_idx}")
                params.append(filters["language"])
                param_idx += 1

            if filters.get("sensitivity"):
                # Filter to include only up to the specified sensitivity level
                sensitivity_levels = {"standard": 1, "sensitive": 2, "highly_sensitive": 3}
                max_level = sensitivity_levels.get(filters["sensitivity"], 1)
                allowed = [k for k, v in sensitivity_levels.items() if v <= max_level]
                where_clauses.append(f"sensitivity = ANY(${param_idx})")
                params.append(allowed)
                param_idx += 1

            if filters.get("location_id"):
                where_clauses.append(f"location_id = ${param_idx}")
                params.append(filters["location_id"])
                param_idx += 1

            if filters.get("museum_id"):
                where_clauses.append(f"museum_id = ${param_idx}")
                params.append(filters["museum_id"])
                param_idx += 1

            if filters.get("route_id"):
                where_clauses.append(f"route_id = ${param_idx}")
                params.append(filters["route_id"])
                param_idx += 1

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"""
            SELECT
                chunk_id,
                source_id,
                source_type,
                text_content,
                language,
                sensitivity,
                1 - (embedding <=> $1::vector) AS similarity_score
            FROM {settings.VECTOR_TABLE}
            {where_sql}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = [
            {
                "chunk_id": row["chunk_id"],
                "source_id": row["source_id"],
                "source_type": row["source_type"],
                "text": row["text_content"],
                "language": row["language"],
                "sensitivity": row["sensitivity"],
                "similarity_score": float(row["similarity_score"]),
            }
            for row in rows
            if float(row["similarity_score"]) >= settings.VECTOR_SIMILARITY_THRESHOLD
        ]

        return results

    async def keyword_search(self, query: str, limit: int = 10) -> list[dict]:
        """
        Keyword fallback using pg_trgm similarity.
        Used when semantic search returns low-confidence results.
        """
        sql = f"""
            SELECT
                chunk_id,
                source_id,
                source_type,
                text_content,
                language,
                sensitivity,
                similarity(text_content, $1) AS trgm_score
            FROM {settings.VECTOR_TABLE}
            WHERE text_content % $1
            ORDER BY trgm_score DESC
            LIMIT $2
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, query, limit)

        return [
            {
                "chunk_id": row["chunk_id"],
                "source_id": row["source_id"],
                "source_type": row["source_type"],
                "text": row["text_content"],
                "language": row["language"],
                "sensitivity": row["sensitivity"],
                "similarity_score": float(row["trgm_score"]),
            }
            for row in rows
        ]

    # ── Delete Embeddings ────────────────────────────────

    async def delete_by_source(self, source_id: str) -> int:
        """Delete all chunks for a given source (e.g., when content is unpublished)."""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {settings.VECTOR_TABLE} WHERE source_id = $1",
                source_id,
            )
            count = int(result.split()[-1])
            logger.info(f"Deleted {count} chunks for source {source_id}")
            return count
