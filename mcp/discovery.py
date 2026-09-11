from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from mcp.registry import ToolMetadata, ToolRegistry


DEFAULT_CACHE_PATH = Path(__file__).resolve().parent.parent / "mcp_tool_cache.json"


@dataclass
class DiscoveryResult:
    """Result of an MCP discovery attempt."""

    tools: list[ToolMetadata]
    source: str
    errors: list[str] = field(default_factory=list)


class MCPDiscovery:
    """Discovers MCP tools and falls back to local project tools."""

    def __init__(
        self,
        server_url: str | None = None,
        cache_path: str | Path | None = None,
        timeout_seconds: int = 5,
    ) -> None:
        self.server_url = (server_url or "").strip()
        self.cache_path = Path(cache_path) if cache_path is not None else DEFAULT_CACHE_PATH
        self.timeout_seconds = max(int(timeout_seconds), 1)
        self.registry = ToolRegistry()

    def discover_tools(self, refresh: bool = False) -> DiscoveryResult:
        if not refresh:
            cached_tools = self._load_cache()
            if cached_tools:
                self.registry.register_many(cached_tools)
                return DiscoveryResult(tools=cached_tools, source="cache")

        errors: list[str] = []
        if self.server_url:
            try:
                remote_tools = self._discover_remote_tools()
                if remote_tools:
                    self.registry.register_many(remote_tools)
                    self._save_cache(remote_tools)
                    return DiscoveryResult(tools=remote_tools, source="mcp")
            except Exception as error:
                errors.append(str(error))

        local_tools = self._discover_local_tools()
        self.registry.register_many(local_tools)
        self._save_cache(local_tools)
        return DiscoveryResult(tools=local_tools, source="local", errors=errors)

    def refresh(self) -> DiscoveryResult:
        return self.discover_tools(refresh=True)

    def health_check(self) -> dict[str, dict[str, Any]]:
        return self.registry.health_check()

    def _discover_remote_tools(self) -> list[ToolMetadata]:
        payload = {
            "jsonrpc": "2.0",
            "id": "tool-discovery",
            "method": "tools/list",
            "params": {},
        }
        request = urllib.request.Request(
            self.server_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise RuntimeError(f"MCP server unavailable: {error.reason}") from error

        try:
            response_body = json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise RuntimeError("MCP server returned invalid JSON.") from error

        if response_body.get("error"):
            raise RuntimeError(f"MCP discovery failed: {response_body['error']}")

        result = response_body.get("result") if isinstance(response_body, dict) else {}
        tools_payload = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools_payload, list):
            raise RuntimeError("MCP discovery response did not include a tools list.")

        return [self._metadata_from_mcp_tool(tool) for tool in tools_payload if isinstance(tool, dict)]

    def _metadata_from_mcp_tool(self, tool: dict[str, Any]) -> ToolMetadata:
        return ToolMetadata.from_dict(
            {
                "tool_name": tool.get("name") or tool.get("tool_name"),
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema") or tool.get("input_schema") or {"type": "object"},
                "output_schema": tool.get("outputSchema") or tool.get("output_schema") or {"type": "object"},
                "permissions": tool.get("permissions", []),
                "availability": tool.get("availability", "active"),
            }
        )

    def _discover_local_tools(self) -> list[ToolMetadata]:
        from pipeline.registry import list_tool_metadata

        return [ToolMetadata.from_dict(tool) for tool in list_tool_metadata()]

    def _load_cache(self) -> list[ToolMetadata]:
        if not self.cache_path.exists():
            return []
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        tools = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                tools.append(ToolMetadata.from_dict(item))
            except ValueError:
                continue
        return tools

    def _save_cache(self, tools: list[ToolMetadata]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps([tool.to_dict() for tool in tools], indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
