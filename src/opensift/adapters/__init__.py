"""Search adapter layer — Pluggable connectors for search backends.

Built-in adapters:
  - atomwalker: AtomWalker ScholarSearch API (academic papers)
  - elasticsearch: Elasticsearch v8+ (BM25 full-text search)
  - opensearch: OpenSearch v2+ (AWS-compatible Elasticsearch fork)
  - solr: Apache Solr v8+ (edismax full-text search)
  - meilisearch: MeiliSearch (instant, typo-tolerant search)

Implement ``SearchAdapter`` to connect your own search backend.
"""
