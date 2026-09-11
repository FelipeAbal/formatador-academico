"""Local web interface for the Formatador Acadêmico."""

from .server import create_server, generate_session_token

__all__ = ["create_server", "generate_session_token"]
