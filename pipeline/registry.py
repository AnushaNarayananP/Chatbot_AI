from __future__ import annotations


def get_tool(name: str):
    return _build_tool_registry()[name]


def list_tool_metadata() -> list[dict]:
    registry = _build_tool_registry()
    return [
        _build_tool_metadata(name, tool)
        for name, tool in registry.items()
    ]


def _build_tool_registry() -> dict:
    from tools.erp_tools import push_invoice_to_erp
    from tools.invoice_tools import extract_invoice_data
    from tools.rag_tools import rag_answer_question
    from tools.storage_tools import store_data
    from tools.text_tools import answer_question, translate_text
    from tools.vision_tools import extract_text_from_image

    tool_registry = {
        "extract_text_from_image": extract_text_from_image,
        "extract_invoice_data": extract_invoice_data,
        "translate_text": translate_text,
        "answer_question": answer_question,
        "store_data": store_data,
        "push_invoice_to_erp": push_invoice_to_erp,
        "rag_answer_question": rag_answer_question,
    }
    return tool_registry


def _build_tool_metadata(name: str, tool) -> dict:
    import inspect

    signature = inspect.signature(tool)
    properties = {}
    required = []
    for parameter_name, parameter in signature.parameters.items():
        properties[parameter_name] = {"type": _json_schema_type(parameter.annotation)}
        if parameter.default is inspect.Parameter.empty:
            required.append(parameter_name)

    return {
        "tool_name": name,
        "description": inspect.getdoc(tool) or f"Local tool: {name}",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        "output_schema": {"type": "object"},
        "permissions": _infer_permissions(name),
        "availability": "active",
    }


def _json_schema_type(annotation) -> str:
    if annotation in {str, "str"}:
        return "string"
    if annotation in {int, "int"}:
        return "integer"
    if annotation in {float, "float"}:
        return "number"
    if annotation in {bool, "bool"}:
        return "boolean"
    if annotation in {dict, "dict"}:
        return "object"
    if annotation in {list, "list"}:
        return "array"
    return "string"


def _infer_permissions(name: str) -> list[str]:
    permission_by_tool = {
        "extract_text_from_image": ["vision_processing", "external_network"],
        "extract_invoice_data": [],
        "translate_text": ["external_network"],
        "answer_question": ["external_network"],
        "store_data": ["write_memory", "write_invoice_database"],
        "push_invoice_to_erp": ["erp_submit"],
        "rag_answer_question": ["external_network", "rag_retrieval"],
    }
    return permission_by_tool.get(name, [])
