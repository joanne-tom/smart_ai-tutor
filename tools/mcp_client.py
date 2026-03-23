# tools/mcp_client.py — Smart AI Tutor MCP Client
#
# Connects to mcp_server.py via stdio transport.
# The server is started once as a subprocess and reused for all calls
# (kept alive for the lifetime of the Flask process).
#
# Usage (synchronous, safe for Flask):
#   from tools.mcp_client import call_mcp_tool
#   result = call_mcp_tool("wikipedia_search", {"query": "semaphore"})

import sys
import os
import asyncio
import threading
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── Path to the MCP server script ──
_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "mcp_server.py")
_SERVER_SCRIPT = os.path.abspath(_SERVER_SCRIPT)

# ── Python executable inside the venv ──
_PYTHON_EXE = sys.executable


# ─────────────────────────────────────────
# Async core — single shared event loop
# ─────────────────────────────────────────

class _MCPClientManager:
    """
    Manages a persistent MCP client session running in a background thread.
    Thread-safe: synchronous callers use call_tool_sync().
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: ClientSession | None = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Start background event loop + MCP session ──
    def _start(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # Wait until the session is ready (or timed out)
        if not self._ready.wait(timeout=30):
            raise RuntimeError("MCP server failed to start within 30 seconds.")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._init_session())

    async def _init_session(self):
        server_params = StdioServerParameters(
            command=_PYTHON_EXE,
            args=[_SERVER_SCRIPT],
            env=None,
        )
        # Keep client context alive for the lifetime of the process
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self._session = session
                self._ready.set()  # signal: ready to use
                # Keep the coroutine alive indefinitely
                await asyncio.get_event_loop().create_future()  # runs forever

    # ── Ensure started (lazy init, only once) ──
    def _ensure_started(self):
        with self._lock:
            if self._session is None:
                self._start()

    # ── Call a tool synchronously ──
    def call_tool_sync(self, tool_name: str, arguments: dict) -> str:
        self._ensure_started()
        future = asyncio.run_coroutine_threadsafe(
            self._call_tool_async(tool_name, arguments),
            self._loop
        )
        try:
            return future.result(timeout=60)
        except Exception as e:
            return f"MCP tool call failed: {str(e)}"

    async def _call_tool_async(self, tool_name: str, arguments: dict) -> str:
        result = await self._session.call_tool(tool_name, arguments)
        # result.content is a list of TextContent / ImageContent etc.
        texts = [
            block.text
            for block in result.content
            if hasattr(block, "text")
        ]
        return "\n".join(texts) if texts else "No result returned by tool."


# ── Singleton instance ──
_manager = _MCPClientManager()


# ─────────────────────────────────────────
# Public API — used by app.py
# ─────────────────────────────────────────

def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """
    Call an MCP tool by name and return its text result.

    Args:
        tool_name:  One of "wikipedia_search", "os_docs_search", "rag_answer"
        arguments:  Dict matching the tool's inputSchema, e.g. {"query": "semaphore"}

    Returns:
        str — the tool's text response, or an error message on failure.
    """
    try:
        return _manager.call_tool_sync(tool_name, arguments)
    except Exception as e:
        return f"MCP client error for tool '{tool_name}': {str(e)}"
