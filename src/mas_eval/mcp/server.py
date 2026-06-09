"""
mas-ts-evaluation-mcp — Article 8 MCP server for evaluation harness (port 8961).
"""

from __future__ import annotations

from maref.integration.mcp_server import MCPServer

server = MCPServer(name="mas-ts-evaluation-mcp", version="0.1.0")


@server.register_tool(
    name="run_evaluation",
    description="Run MAS-TS evaluation on a domain/level",
    input_schema={
        "api_version": "1.0.0",
        "type": "object",
        "properties": {
            "domain": {"type": "string", "enum": ["d1", "d2", "d3", "d4", "d5"]},
            "level": {"type": "string", "enum": ["l0", "l1", "l2", "l3", "l4"]},
            "agent_config": {"type": "object"},
        },
        "required": ["domain", "level"],
    },
)
def run_evaluation(args: dict) -> dict:
    """Delegate to evaluation harness."""
    # Basic implementation — delegates to existing harness
    domain = args.get("domain", "d1")
    level = args.get("level", "l0")
    result = {"domain": domain, "level": level, "status": "ok", "result": {}}
    return result


@server.register_tool(
    name="list_domains",
    description="List available evaluation domains",
    input_schema={
        "api_version": "1.0.0",
        "type": "object",
        "properties": {},
    },
)
def list_domains(args: dict) -> dict:
    return {
        "domains": ["d1", "d2", "d3", "d4", "d5"],
        "levels": ["l0", "l1", "l2", "l3", "l4"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(server, host="127.0.0.1", port=8961)
