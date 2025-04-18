from unittest.mock import Mock

import pytest
from haystack.dataclasses import Document, SparseEmbedding
from haystack.document_stores.types import FilterPolicy

from haystack_integrations.components.retrievers.qdrant import (
    QdrantHybridRetriever,
)
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore


class TestQdrantHybridRetriever:
    def test_init_default(self):
        document_store = QdrantDocumentStore(location=":memory:", index="test", use_sparse_embeddings=True)
        retriever = QdrantHybridRetriever(document_store=document_store)

        assert retriever._document_store == document_store
        assert retriever._filters is None
        assert retriever._top_k == 10
        assert retriever._filter_policy == FilterPolicy.REPLACE
        assert retriever._return_embedding is False
        assert retriever._score_threshold is None
        assert retriever._group_by is None
        assert retriever._group_size is None

        retriever = QdrantHybridRetriever(document_store=document_store, filter_policy="replace")
        assert retriever._filter_policy == FilterPolicy.REPLACE

        with pytest.raises(ValueError):
            QdrantHybridRetriever(document_store=document_store, filter_policy="invalid")

    def test_to_dict(self):
        document_store = QdrantDocumentStore(location=":memory:", index="test")
        retriever = QdrantHybridRetriever(document_store=document_store, top_k=5, return_embedding=True)
        res = retriever.to_dict()
        assert res == {
            "type": "haystack_integrations.components.retrievers.qdrant.retriever.QdrantHybridRetriever",
            "init_parameters": {
                "document_store": {
                    "type": "haystack_integrations.document_stores.qdrant.document_store.QdrantDocumentStore",
                    "init_parameters": {
                        "location": ":memory:",
                        "url": None,
                        "port": 6333,
                        "grpc_port": 6334,
                        "prefer_grpc": False,
                        "https": None,
                        "api_key": None,
                        "prefix": None,
                        "timeout": None,
                        "host": None,
                        "path": None,
                        "index": "test",
                        "embedding_dim": 768,
                        "on_disk": False,
                        "force_disable_check_same_thread": False,
                        "use_sparse_embeddings": False,
                        "sparse_idf": False,
                        "similarity": "cosine",
                        "return_embedding": False,
                        "progress_bar": True,
                        "recreate_index": False,
                        "shard_number": None,
                        "replication_factor": None,
                        "write_consistency_factor": None,
                        "on_disk_payload": None,
                        "hnsw_config": None,
                        "optimizers_config": None,
                        "wal_config": None,
                        "quantization_config": None,
                        "init_from": None,
                        "wait_result_from_api": True,
                        "metadata": {},
                        "write_batch_size": 100,
                        "scroll_size": 10000,
                        "payload_fields_to_index": None,
                    },
                },
                "filters": None,
                "top_k": 5,
                "filter_policy": "replace",
                "return_embedding": True,
                "score_threshold": None,
                "group_by": None,
                "group_size": None,
            },
        }

    def test_from_dict(self):
        data = {
            "type": "haystack_integrations.components.retrievers.qdrant.retriever.QdrantHybridRetriever",
            "init_parameters": {
                "document_store": {
                    "init_parameters": {"location": ":memory:", "index": "test"},
                    "type": "haystack_integrations.document_stores.qdrant.document_store.QdrantDocumentStore",
                },
                "filters": None,
                "top_k": 5,
                "filter_policy": "replace",
                "return_embedding": True,
                "score_threshold": None,
                "group_by": None,
                "group_size": None,
            },
        }
        retriever = QdrantHybridRetriever.from_dict(data)
        assert isinstance(retriever._document_store, QdrantDocumentStore)
        assert retriever._document_store.index == "test"
        assert retriever._filters is None
        assert retriever._top_k == 5
        assert retriever._filter_policy == FilterPolicy.REPLACE
        assert retriever._return_embedding
        assert retriever._score_threshold is None
        assert retriever._group_by is None
        assert retriever._group_size is None

    def test_from_dict_no_filter_policy(self):
        data = {
            "type": "haystack_integrations.components.retrievers.qdrant.retriever.QdrantHybridRetriever",
            "init_parameters": {
                "document_store": {
                    "init_parameters": {"location": ":memory:", "index": "test"},
                    "type": "haystack_integrations.document_stores.qdrant.document_store.QdrantDocumentStore",
                },
                "filters": None,
                "top_k": 5,
                "return_embedding": True,
                "score_threshold": None,
                "group_by": None,
                "group_size": None,
            },
        }
        retriever = QdrantHybridRetriever.from_dict(data)
        assert isinstance(retriever._document_store, QdrantDocumentStore)
        assert retriever._document_store.index == "test"
        assert retriever._filters is None
        assert retriever._top_k == 5
        assert retriever._filter_policy == FilterPolicy.REPLACE  # defaults to REPLACE
        assert retriever._return_embedding
        assert retriever._score_threshold is None
        assert retriever._group_by is None
        assert retriever._group_size is None

    def test_run(self):
        mock_store = Mock(spec=QdrantDocumentStore)
        sparse_embedding = SparseEmbedding(indices=[0, 1, 2, 3], values=[0.1, 0.8, 0.05, 0.33])
        mock_store._query_hybrid.return_value = [
            Document(content="Test doc", embedding=[0.1, 0.2], sparse_embedding=sparse_embedding)
        ]

        retriever = QdrantHybridRetriever(document_store=mock_store)
        res = retriever.run(
            query_embedding=[0.5, 0.7], query_sparse_embedding=SparseEmbedding(indices=[0, 5], values=[0.1, 0.7])
        )

        call_args = mock_store._query_hybrid.call_args
        assert call_args[1]["query_embedding"] == [0.5, 0.7]
        assert call_args[1]["query_sparse_embedding"].indices == [0, 5]
        assert call_args[1]["query_sparse_embedding"].values == [0.1, 0.7]
        assert call_args[1]["top_k"] == 10
        assert call_args[1]["return_embedding"] is False

        assert res["documents"][0].content == "Test doc"
        assert res["documents"][0].embedding == [0.1, 0.2]
        assert res["documents"][0].sparse_embedding == sparse_embedding

    def test_run_with_group_by(self):
        mock_store = Mock(spec=QdrantDocumentStore)
        sparse_embedding = SparseEmbedding(indices=[0, 1, 2, 3], values=[0.1, 0.8, 0.05, 0.33])
        mock_store._query_hybrid.return_value = [
            Document(content="Test doc", embedding=[0.1, 0.2], sparse_embedding=sparse_embedding)
        ]

        retriever = QdrantHybridRetriever(document_store=mock_store)
        res = retriever.run(
            query_embedding=[0.5, 0.7],
            query_sparse_embedding=SparseEmbedding(indices=[0, 5], values=[0.1, 0.7]),
            group_by="meta.group_field",
            group_size=2,
        )

        call_args = mock_store._query_hybrid.call_args
        assert call_args[1]["query_embedding"] == [0.5, 0.7]
        assert call_args[1]["query_sparse_embedding"].indices == [0, 5]
        assert call_args[1]["query_sparse_embedding"].values == [0.1, 0.7]
        assert call_args[1]["top_k"] == 10
        assert call_args[1]["return_embedding"] is False
        assert call_args[1]["group_by"] == "meta.group_field"
        assert call_args[1]["group_size"] == 2

        assert res["documents"][0].content == "Test doc"
        assert res["documents"][0].embedding == [0.1, 0.2]
        assert res["documents"][0].sparse_embedding == sparse_embedding

    @pytest.mark.asyncio
    async def test_run_async(self):
        mock_store = Mock(spec=QdrantDocumentStore)
        sparse_embedding = SparseEmbedding(indices=[0, 1, 2, 3], values=[0.1, 0.8, 0.05, 0.33])
        mock_store._query_hybrid_async.return_value = [
            Document(content="Test doc", embedding=[0.1, 0.2], sparse_embedding=sparse_embedding)
        ]

        retriever = QdrantHybridRetriever(document_store=mock_store)
        result = await retriever.run_async(
            query_embedding=[0.5, 0.7], query_sparse_embedding=SparseEmbedding(indices=[0, 5], values=[0.1, 0.7])
        )

        call_args = mock_store._query_hybrid_async.call_args
        assert call_args[1]["query_embedding"] == [0.5, 0.7]
        assert call_args[1]["query_sparse_embedding"].indices == [0, 5]
        assert call_args[1]["query_sparse_embedding"].values == [0.1, 0.7]
        assert call_args[1]["top_k"] == 10
        assert call_args[1]["return_embedding"] is False

        assert result["documents"][0].content == "Test doc"
        assert result["documents"][0].embedding == [0.1, 0.2]
        assert result["documents"][0].sparse_embedding == sparse_embedding

    @pytest.mark.asyncio
    async def test_run_with_group_by_async(self):
        mock_store = Mock(spec=QdrantDocumentStore)
        sparse_embedding = SparseEmbedding(indices=[0, 1, 2, 3], values=[0.1, 0.8, 0.05, 0.33])
        mock_store._query_hybrid_async.return_value = [
            Document(content="Test doc", embedding=[0.1, 0.2], sparse_embedding=sparse_embedding)
        ]

        retriever = QdrantHybridRetriever(document_store=mock_store)
        result = await retriever.run_async(
            query_embedding=[0.5, 0.7],
            query_sparse_embedding=SparseEmbedding(indices=[0, 5], values=[0.1, 0.7]),
            group_by="meta.group_field",
            group_size=2,
        )

        call_args = mock_store._query_hybrid_async.call_args
        assert call_args[1]["query_embedding"] == [0.5, 0.7]
        assert call_args[1]["query_sparse_embedding"].indices == [0, 5]
        assert call_args[1]["query_sparse_embedding"].values == [0.1, 0.7]
        assert call_args[1]["top_k"] == 10
        assert call_args[1]["return_embedding"] is False
        assert call_args[1]["group_by"] == "meta.group_field"
        assert call_args[1]["group_size"] == 2

        assert result["documents"][0].content == "Test doc"
        assert result["documents"][0].embedding == [0.1, 0.2]
        assert result["documents"][0].sparse_embedding == sparse_embedding
