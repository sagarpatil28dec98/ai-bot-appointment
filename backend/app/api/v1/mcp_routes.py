"""
FastAPI Routes for Model Context Protocol (MCP) and Multi-Channel Inbound Webhooks.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from app.mcp.server import mcp_server

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])

@router.get("/tools")
async def list_mcp_tools() -> List[Dict[str, Any]]:
    """Returns the list of available MCP tools and schemas."""
    return mcp_server.list_tools()

@router.post("/call")
async def call_mcp_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a requested MCP tool with given arguments.
    Expected JSON: {"name": "check_doctor_availability", "arguments": {...}}
    """
    tool_name = payload.get("name")
    arguments = payload.get("arguments", {})

    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool 'name' is required.")

    result = await mcp_server.call_tool(name=tool_name, arguments=arguments)
    return {"content": [{"type": "text", "text": str(result)}], "is_error": "error" in result}
