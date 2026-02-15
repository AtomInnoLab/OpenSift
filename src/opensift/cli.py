"""CLI entry point for OpenSift server."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main() -> None:
    """Main CLI entry point for the OpenSift server."""
    parser = argparse.ArgumentParser(
        prog="opensift",
        description="OpenSift — AI-Powered Search Augmentation Layer",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Server bind address (overrides config)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Server port (overrides config)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="Number of worker processes",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error"],
        default=None,
        help="Log level (overrides config)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"OpenSift {_get_version()}",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = (args.log_level or "info").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load settings
    from opensift.config.settings import Settings

    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
        settings = Settings.from_yaml(config_path)
    else:
        settings = Settings()

    # Apply CLI overrides
    if args.host:
        settings.server.host = args.host
    if args.port:
        settings.server.port = args.port
    if args.workers:
        settings.server.workers = args.workers
    if args.log_level:
        settings.observability.log_level = args.log_level

    # Start server
    import uvicorn

    uvicorn.run(
        "opensift.api.app:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers if not args.reload else 1,
        reload=args.reload,
        log_level=log_level.lower(),
    )


def _get_version() -> str:
    """Get the package version."""
    try:
        from opensift import __version__

        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    main()
