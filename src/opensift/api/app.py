"""FastAPI application factory and lifecycle management."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from opensift import __version__
from opensift.api.deps import set_engine
from opensift.api.v1.router import router as v1_router
from opensift.config.settings import Settings
from opensift.core.engine import OpenSiftEngine

_STATIC_DIR = Path(__file__).parent / "static"

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Application settings. If None, loads from environment.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        # Auto-detect opensift-config.yaml if present
        yaml_path = Path("opensift-config.yaml")
        if yaml_path.exists():
            logger.info("Loading configuration from %s", yaml_path)
            settings = Settings.from_yaml(yaml_path)
        else:
            settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Manage application lifecycle (startup/shutdown)."""
        logger.info("Starting OpenSift v%s", __version__)

        # Initialize engine
        engine = OpenSiftEngine(settings)
        await engine.initialize()

        # Auto-register adapters from configuration
        await _register_adapters(engine, settings)

        set_engine(engine)

        # Store settings in app state
        app.state.settings = settings
        app.state.engine = engine

        logger.info("OpenSift is ready to serve requests on port %d", settings.server.port)
        yield

        # Shutdown
        logger.info("Shutting down OpenSift...")
        await engine.shutdown()
        set_engine(None)
        logger.info("OpenSift shutdown complete")

    app = FastAPI(
        title="OpenSift",
        description=(
            "Open-source AI augmentation layer for search engines — "
            "adds intelligent query planning and result verification to any search backend."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(v1_router, prefix="/v1")

    # ── Debug Panel (Web UI) ──────────────────────────────────────────────
    @app.get("/debug", include_in_schema=False)
    async def debug_panel() -> FileResponse:
        """Serve the Web UI debug panel."""
        return FileResponse(_STATIC_DIR / "debug.html", media_type="text/html")

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


# ── Adapter auto-registration ──

# Maps adapter names to (module_path, class_name) for lazy import
_ADAPTER_MAP: dict[str, tuple[str, str]] = {
    "elasticsearch": ("opensift.adapters.elasticsearch.adapter", "ElasticsearchAdapter"),
    "atomwalker": ("opensift.adapters.atomwalker.adapter", "AtomWalkerAdapter"),
    "opensearch": ("opensift.adapters.opensearch.adapter", "OpenSearchAdapter"),
    "solr": ("opensift.adapters.solr.adapter", "SolrAdapter"),
    "meilisearch": ("opensift.adapters.meilisearch.adapter", "MeiliSearchAdapter"),
    "wikipedia": ("opensift.adapters.wikipedia.adapter", "WikipediaAdapter"),
}


async def _register_adapters(engine: OpenSiftEngine, settings: Settings) -> None:
    """Register and initialise adapters declared in settings.

    For each adapter entry in ``settings.search.adapters`` that is enabled,
    the corresponding adapter class is imported, registered, and initialised.
    """
    for adapter_name, adapter_cfg in settings.search.adapters.items():
        if not adapter_cfg.enabled:
            logger.info("Adapter '%s' is disabled, skipping", adapter_name)
            continue

        entry = _ADAPTER_MAP.get(adapter_name)
        if entry is None:
            logger.warning(
                "Unknown adapter '%s' — no built-in class found. "
                "Register it manually via engine.adapter_registry.register().",
                adapter_name,
            )
            continue

        module_path, class_name = entry
        try:
            import importlib

            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.warning("Failed to import adapter '%s': %s", adapter_name, e)
            continue

        # Build constructor kwargs from AdapterConfig
        # Different adapters expect different constructor parameter names.
        url_adapters = {"atomwalker", "solr", "meilisearch"}
        collection_adapters = {"solr"}  # uses 'collection' instead of 'index'

        kwargs: dict[str, object] = {}

        # Wikipedia uses 'language' from index_pattern and has no hosts
        if adapter_name == "wikipedia":
            if adapter_cfg.index_pattern and adapter_cfg.index_pattern != "*":
                kwargs["language"] = adapter_cfg.index_pattern
        else:
            if adapter_cfg.hosts:
                if adapter_name in url_adapters:
                    kwargs["base_url"] = adapter_cfg.hosts[0]
                else:
                    kwargs["hosts"] = adapter_cfg.hosts
            if adapter_cfg.index_pattern and adapter_cfg.index_pattern != "*":
                if adapter_name in collection_adapters:
                    kwargs["collection"] = adapter_cfg.index_pattern
                elif adapter_name in {"atomwalker", "meilisearch"}:
                    kwargs["index"] = adapter_cfg.index_pattern
                else:
                    kwargs["index_pattern"] = adapter_cfg.index_pattern
        if adapter_cfg.api_key:
            kwargs["api_key"] = adapter_cfg.api_key
        if adapter_cfg.username:
            kwargs["username"] = adapter_cfg.username
        if adapter_cfg.password:
            kwargs["password"] = adapter_cfg.password
        # Pass through any extra config
        kwargs.update(adapter_cfg.extra)

        engine.adapter_registry.register(adapter_name, adapter_class)
        try:
            await engine.adapter_registry.initialize_adapter(adapter_name, **kwargs)
            logger.info("Adapter '%s' registered and initialised", adapter_name)
        except Exception:
            logger.warning(
                "Failed to initialise adapter '%s'",
                adapter_name,
                exc_info=True,
            )
