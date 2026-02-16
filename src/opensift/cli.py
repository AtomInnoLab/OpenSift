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

    # Check port availability before starting
    _check_port(settings.server.host, settings.server.port)

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


def _check_port(host: str, port: int) -> None:
    """Check if the port is available. If not, print the blocking process and exit."""
    import socket
    import subprocess

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host if host != "0.0.0.0" else "127.0.0.1", port))
    except OSError:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"  ERROR: Port {port} is already in use!", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)

        # Try lsof to find the process occupying the port
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-P", "-n"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip():
                print(f"\n  Processes using port {port}:\n", file=sys.stderr)
                for line in result.stdout.strip().splitlines():
                    print(f"    {line}", file=sys.stderr)

                # Extract PIDs for kill hint
                pids = set()
                for line in result.stdout.strip().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        pids.add(parts[1])
                if pids:
                    pid_str = " ".join(sorted(pids))
                    print("\n  To free the port, run:", file=sys.stderr)
                    print(f"    kill {pid_str}", file=sys.stderr)
                    print("  Or force kill:", file=sys.stderr)
                    print(f"    kill -9 {pid_str}", file=sys.stderr)
            else:
                print(f"\n  Could not identify the process using port {port}.", file=sys.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"\n  Run 'lsof -i :{port}' to find the process.", file=sys.stderr)

        print(f"\n{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)
    finally:
        sock.close()


def _get_version() -> str:
    """Get the package version."""
    try:
        from opensift import __version__

        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    main()
