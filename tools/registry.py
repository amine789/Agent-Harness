from dataclasses import dataclass
from typing import Any, Callable
from pydantic import TypeAdapter
import inspect


@dataclass
class Tool:
    """A registered tool — wraps a Python function with its metadata."""
    name: str
    description: str
    function: Callable
    schema: dict

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tool]= {}


    def register(self, tool):
        self._tools[tool.name] = tool

    def get_schemas(self):
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.schema,
            }
            for t in self._tools.values()
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
       if name not in self._tools:
        return f"error: unknown tool '{name}'"

       try:
           result = self._tools[name].function(**arguments)
           return str(result)
       except Exception as e:
           return f"error {type(e).__name__}: {e}"



# The single global registry the rest of the harness imports.
registry = ToolRegistry()

def tool(func: Callable) -> Callable:
    """
    Decorator: register a function as a tool.

    Reads the function's name, docstring, and type-hinted parameters
    to build the tool's input schema. Adds it to the global registry.
    """
    # Step 1: extract metadata from the function itself.
    name = func.__name__
    description = inspect.getdoc(func) or ""

    # Step 2: build a JSON schema for the function's parameters via pydantic.
    # TypeAdapter introspects the signature and produces a JSON schema, used
    # directly as Anthropic's input_schema.
    schema = TypeAdapter(func).json_schema()

    # Step 3: register the tool in the global registry.
    registry.register(Tool(
        name=name,
        description=description,
        function=func,
        schema=schema,
    ))

    # Step 4: return the function unchanged so it can still be called directly.
    return func