"""Integration test fixtures — Docker-based search backends with mock data.

Expects backends to be running via:
    docker compose -f deployments/docker/docker-compose.test.yml up -d

Seed data is automatically loaded into each backend on first use.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

import httpx
import pytest

MOCK_DOCUMENTS: list[dict[str, Any]] = [
    {
        "id": "doc-001",
        "title": "Advances in Solar Nowcasting Using Deep Learning",
        "content": (
            "This paper presents a novel deep learning approach for solar irradiance "
            "nowcasting. We propose a convolutional neural network architecture that "
            "processes satellite imagery to predict solar irradiance up to 4 hours ahead. "
            "Experiments on the NSRDB dataset show our method achieves 15% lower RMSE "
            "compared to persistence models."
        ),
        "author": "Alice Johnson",
        "url": "https://example.com/papers/solar-nowcasting-dl",
        "tags": ["solar energy", "deep learning", "nowcasting"],
        "published_date": "2024-06-15T00:00:00Z",
    },
    {
        "id": "doc-002",
        "title": "Transformer Models for Natural Language Understanding",
        "content": (
            "We survey recent advances in transformer-based models for natural language "
            "understanding tasks. The paper covers BERT, GPT, T5, and their variants, "
            "analyzing performance on GLUE, SuperGLUE, and SQuAD benchmarks. We find that "
            "scaling model parameters consistently improves downstream task performance."
        ),
        "author": "Bob Smith",
        "url": "https://example.com/papers/transformers-nlu",
        "tags": ["NLP", "transformers", "language models"],
        "published_date": "2024-03-20T00:00:00Z",
    },
    {
        "id": "doc-003",
        "title": "Federated Learning for Privacy-Preserving Medical Imaging",
        "content": (
            "This study explores federated learning techniques for training medical "
            "image classification models without sharing patient data. We demonstrate "
            "that federated averaging across 12 hospital sites achieves diagnostic "
            "accuracy within 2% of centralized training while preserving patient privacy."
        ),
        "author": "Carol Zhang",
        "url": "https://example.com/papers/federated-medical",
        "tags": ["federated learning", "medical imaging", "privacy"],
        "published_date": "2024-09-01T00:00:00Z",
    },
    {
        "id": "doc-004",
        "title": "Reinforcement Learning for Robotic Manipulation",
        "content": (
            "We present a sim-to-real reinforcement learning framework for dexterous "
            "robotic manipulation. Using domain randomization and progressive training, "
            "our policy transfers to a real robotic hand with a 78% task success rate "
            "on pick-and-place operations."
        ),
        "author": "David Lee",
        "url": "https://example.com/papers/rl-robotics",
        "tags": ["reinforcement learning", "robotics", "manipulation"],
        "published_date": "2024-01-10T00:00:00Z",
    },
    {
        "id": "doc-005",
        "title": "Graph Neural Networks for Drug Discovery",
        "content": (
            "This work applies graph neural networks to molecular property prediction "
            "for drug discovery. We introduce a novel message-passing architecture that "
            "captures 3D molecular geometry and achieves state-of-the-art results on "
            "the MoleculeNet benchmark suite."
        ),
        "author": "Eve Brown",
        "url": "https://example.com/papers/gnn-drug",
        "tags": ["graph neural networks", "drug discovery", "molecular"],
        "published_date": "2024-07-22T00:00:00Z",
    },
]


def _wait_for_service(url: str, timeout: float = 120.0) -> bool:
    """Block until *url* returns HTTP 200, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=30)
            if r.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


# ── Elasticsearch ───────────────────────────────────────────────


async def _seed_elasticsearch(host: str = "http://localhost:9200", index: str = "test-docs") -> None:
    async with httpx.AsyncClient(base_url=host, timeout=30) as client:
        # Delete index if exists
        await client.delete(f"/{index}", params={"ignore_unavailable": "true"})

        mapping = {
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "author": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "published_date": {"type": "date"},
                }
            }
        }
        resp = await client.put(f"/{index}", json=mapping)
        resp.raise_for_status()

        # Index documents
        for doc in MOCK_DOCUMENTS:
            resp = await client.put(f"/{index}/_doc/{doc['id']}", json=doc)
            resp.raise_for_status()

        # Refresh to make searchable
        await client.post(f"/{index}/_refresh")


@pytest.fixture(scope="session")
def elasticsearch_ready():
    """Ensure Elasticsearch is running and seeded."""
    host = "http://localhost:9200"
    if not _wait_for_service(host):
        pytest.skip("Elasticsearch not available at localhost:9200")
    asyncio.run(_seed_elasticsearch(host))
    return host


# ── OpenSearch ──────────────────────────────────────────────────


async def _seed_opensearch(host: str = "http://localhost:9201", index: str = "test-docs") -> None:
    async with httpx.AsyncClient(base_url=host, timeout=30) as client:
        await client.delete(f"/{index}", params={"ignore_unavailable": "true"})

        mapping = {
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "author": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "published_date": {"type": "date"},
                }
            }
        }
        resp = await client.put(f"/{index}", json=mapping)
        resp.raise_for_status()

        for doc in MOCK_DOCUMENTS:
            resp = await client.put(f"/{index}/_doc/{doc['id']}", json=doc)
            resp.raise_for_status()

        await client.post(f"/{index}/_refresh")


@pytest.fixture(scope="session")
def opensearch_ready():
    """Ensure OpenSearch is running and seeded."""
    host = "http://localhost:9201"
    if not _wait_for_service(host):
        pytest.skip("OpenSearch not available at localhost:9201")
    asyncio.run(_seed_opensearch(host))
    return host


# ── Solr ────────────────────────────────────────────────────────


async def _seed_solr(
    host: str = "http://localhost:8983/solr",
    collection: str = "documents",
) -> None:
    async with httpx.AsyncClient(base_url=host, timeout=30) as client:
        # Add fields to schema (Solr needs explicit schema for non-dynamic fields)
        for field in [
            {"name": "title", "type": "text_general", "stored": True},
            {"name": "content", "type": "text_general", "stored": True},
            {"name": "description", "type": "text_general", "stored": True},
            {"name": "author", "type": "string", "stored": True},
            {"name": "url", "type": "string", "stored": True},
            {"name": "tags", "type": "strings", "stored": True},
            {"name": "published_date", "type": "pdate", "stored": True},
        ]:
            with contextlib.suppress(httpx.HTTPError):
                await client.post(
                    f"/{collection}/schema",
                    json={"add-field": field},
                )

        # Delete all existing docs
        await client.post(
            f"/{collection}/update",
            json={"delete": {"query": "*:*"}},
            params={"commit": "true"},
        )

        # Index documents
        solr_docs = []
        for doc in MOCK_DOCUMENTS:
            solr_docs.append(doc)

        resp = await client.post(
            f"/{collection}/update",
            json=solr_docs,
            params={"commit": "true"},
        )
        resp.raise_for_status()


@pytest.fixture(scope="session")
def solr_ready():
    """Ensure Solr is running and seeded."""
    host = "http://localhost:8983/solr"
    if not _wait_for_service(f"{host}/documents/admin/ping", timeout=90.0):
        pytest.skip("Solr not available at localhost:8983")
    asyncio.run(_seed_solr(host))
    return host


# ── MeiliSearch ─────────────────────────────────────────────────


async def _seed_meilisearch(
    host: str = "http://localhost:7700",
    index: str = "test-docs",
    api_key: str = "test-master-key",
) -> None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(base_url=host, timeout=30, headers=headers) as client:
        # Delete index if exists
        await client.delete(f"/indexes/{index}")
        await asyncio.sleep(0.5)

        # Create index
        resp = await client.post("/indexes", json={"uid": index, "primaryKey": "id"})
        resp.raise_for_status()
        await asyncio.sleep(0.5)

        # Configure filterable/sortable attributes
        await client.patch(
            f"/indexes/{index}/settings",
            json={
                "filterableAttributes": ["tags", "author", "timestamp"],
                "sortableAttributes": ["published_date"],
                "searchableAttributes": ["title", "content", "author", "tags"],
            },
        )
        await asyncio.sleep(0.5)

        # Add documents
        resp = await client.post(f"/indexes/{index}/documents", json=MOCK_DOCUMENTS)
        resp.raise_for_status()

        # Wait for indexing to complete
        task = resp.json()
        task_uid = task.get("taskUid")
        if task_uid is not None:
            for _ in range(30):
                t = await client.get(f"/tasks/{task_uid}")
                status = t.json().get("status")
                if status in ("succeeded", "failed"):
                    break
                await asyncio.sleep(0.5)


@pytest.fixture(scope="session")
def meilisearch_ready():
    """Ensure MeiliSearch is running and seeded."""
    host = "http://localhost:7700"
    if not _wait_for_service(f"{host}/health"):
        pytest.skip("MeiliSearch not available at localhost:7700")
    asyncio.run(_seed_meilisearch(host))
    return host
