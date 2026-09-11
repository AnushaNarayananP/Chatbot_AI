from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolMetadata:
    """Normalized metadata for a local or MCP-provided tool."""

    tool_name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    permissions: list[str] = field(default_factory=list)
    availability: str = "active"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolMetadata":
        name = str(data.get("tool_name") or data.get("name") or "").strip()
        if not name:
            raise ValueError("Tool metadata is missing tool_name.")
        return cls(
            tool_name=name,
            description=str(data.get("description") or "").strip(),
            input_schema=_schema_or_default(data.get("input_schema")),
            output_schema=_schema_or_default(data.get("output_schema")),
            permissions=_permissions_or_default(data.get("permissions")),
            availability=str(data.get("availability") or "active").strip() or "active",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolRegistry:
    """In-memory registry for discovered tool metadata."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}

    def register(self, metadata: ToolMetadata | dict[str, Any]) -> ToolMetadata:
        tool = metadata if isinstance(metadata, ToolMetadata) else ToolMetadata.from_dict(metadata)
        self._tools[tool.tool_name] = tool
        return tool

    def register_many(self, tools: list[ToolMetadata | dict[str, Any]]) -> list[ToolMetadata]:
        return [self.register(tool) for tool in tools]

    def get(self, tool_name: str) -> ToolMetadata:
        return self._tools[tool_name]

    def list_tools(self) -> list[ToolMetadata]:
        return list(self._tools.values())

    def list_active(self) -> list[ToolMetadata]:
        return [tool for tool in self._tools.values() if tool.availability == "active"]

    def mark_inactive(self, tool_name: str) -> None:
        self._tools[tool_name].availability = "inactive"

    def mark_active(self, tool_name: str) -> None:
        self._tools[tool_name].availability = "active"

    def health_check(self) -> dict[str, dict[str, Any]]:
        return {
            tool.tool_name: {
                "availability": tool.availability,
                "healthy": tool.availability == "active",
                "permissions": tool.permissions,
            }
            for tool in self._tools.values()
        }


def _schema_or_default(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {"type": "object"}


def _permissions_or_default(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
