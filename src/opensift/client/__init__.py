"""OpenSift Python SDK — Client library for the OpenSift API.

Provides both async and sync clients for interacting with an OpenSift server.

Quick start::

    from opensift.client import OpenSiftClient

    client = OpenSiftClient("http://localhost:8080")

    # Complete mode
    response = client.search("solar nowcasting deep learning")

    # Streaming mode
    for event in client.search_stream("solar nowcasting deep learning"):
        print(event)
"""

from opensift.client.client import AsyncOpenSiftClient, OpenSiftClient

__all__ = ["AsyncOpenSiftClient", "OpenSiftClient"]
