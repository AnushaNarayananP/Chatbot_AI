from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from mcp.discovery import MCPDiscovery
from mcp.registry import ToolRegistry


def test_discovery_falls_back_to_local_registry_when_mcp_server_unavailable():
    tmp_dir = tempfile.mkdtemp(prefix="chatbot-test-")
    try:
        discovery = MCPDiscovery(
            server_url="http://127.0.0.1:1/mcp",
            cache_path=Path(tmp_dir) / "tool_cache.json",
        )

        result = discovery.discover_tools(refresh=True)

        assert result.source == "local"
        assert result.errors
        assert result.tools
        names = {tool.tool_name for tool in result.tools}
        assert "extract_invoice_data" in names
        invoice_tool = next(tool for tool in result.tools if tool.tool_name == "extract_invoice_data")
        assert invoice_tool.availability == "active"
        assert invoice_tool.input_schema["type"] == "object"
        assert isinstance(invoice_tool.permissions, list)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_discovery_uses_cached_metadata_when_refresh_is_false():
    tmp_dir = tempfile.mkdtemp(prefix="chatbot-test-")
    try:
        cache_path = Path(tmp_dir) / "tool_cache.json"
        cache_path.write_text(
            json.dumps(
                [
                    {
                        "tool_name": "cached_tool",
                        "description": "Loaded from cache",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                        "permissions": ["read_memory"],
                        "availability": "active",
                    }
                ]
            ),
            encoding="utf-8",
        )
        discovery = MCPDiscovery(
            server_url="http://127.0.0.1:1/mcp",
            cache_path=cache_path,
        )

        result = discovery.discover_tools(refresh=False)

        assert result.source == "cache"
        assert [tool.tool_name for tool in result.tools] == ["cached_tool"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_tool_registry_tracks_health_and_active_state():
    registry = ToolRegistry()
    registry.register(
        {
            "tool_name": "sample_tool",
            "description": "A sample tool",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "permissions": [],
            "availability": "active",
        }
    )

    assert registry.health_check()["sample_tool"]["availability"] == "active"

    registry.mark_inactive("sample_tool")

    assert registry.get("sample_tool").availability == "inactive"
    assert registry.list_active() == []
