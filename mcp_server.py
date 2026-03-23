# mcp_server.py — Smart AI Tutor MCP Tool Server
# Run standalone: python mcp_server.py
# Communicates over stdio using the MCP protocol.

import sys
import os
import asyncio

# ── Make sure project root is on the path ──
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "RAG_steps"))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── Import the actual tool logic ──
from tools.mcp_tools import wiki_search, os_docs_search
from tools.rag_tool import rag_answer

# ─────────────────────────────────────────
# Create the MCP Server
# ─────────────────────────────────────────
server = Server("smart-ai-tutor-tools")


# ─────────────────────────────────────────
# Declare available tools
# ─────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="wikipedia_search",
            description=(
                "Search Wikipedia for a summary of a topic. "
                "Best for real-world context, analogies, or application-level questions "
                "not directly related to OS internals."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic or question to search Wikipedia for."
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="os_docs_search",
            description=(
                "Search Linux / POSIX OS documentation for a query. "
                "Uses tldr-pages, man7.org, and Wikipedia with OS context. "
                "Best for system calls, kernel concepts, Linux commands, POSIX APIs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The OS concept, system call, or Linux command to look up."
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="rag_answer",
            description=(
                "Answer a question using the RAG (Retrieval-Augmented Generation) pipeline "
                "over the student's uploaded lecture notes. "
                "Best for concept questions, misconceptions, and anything directly in the syllabus."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The student question to answer from the indexed notes."
                    }
                },
                "required": ["query"]
            }
        ),
    ]


# ─────────────────────────────────────────
# Handle tool calls
# ─────────────────────────────────────────
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    query = arguments.get("query", "").strip()

    if not query:
        return [types.TextContent(type="text", text="Error: 'query' argument is required.")]

    try:
        if name == "wikipedia_search":
            result = await asyncio.to_thread(wiki_search, query)

        elif name == "os_docs_search":
            result = await asyncio.to_thread(os_docs_search, query)

        elif name == "rag_answer":
            result = await asyncio.to_thread(rag_answer, query)

        else:
            result = f"Unknown tool: '{name}'. Available tools: wikipedia_search, os_docs_search, rag_answer."

    except Exception as e:
        result = f"Tool '{name}' encountered an error: {str(e)}"

    return [types.TextContent(type="text", text=result)]


# ─────────────────────────────────────────
# Entry point — run via stdio transport
# ─────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
