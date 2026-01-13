#!/usr/bin/env python3
"""
Custom Notion MCP Server

Provides structured database querying with filters, sorts, and pagination
that works on any Notion plan (not just Enterprise).
"""

import asyncio
import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Constants
NOTION_API_VERSION = "2022-06-28"
NOTION_API_VERSION_NEW = "2025-09-03"  # Required for multi-data-source databases
NOTION_BASE_URL = "https://api.notion.com/v1"
MAX_TEXT_SIZE = 100_000
MAX_LIST_ITEMS = 100


def get_api_key() -> str:
    """Get Notion API key from environment."""
    key = os.environ.get("NOTION_API_KEY")
    if not key:
        raise ValueError("NOTION_API_KEY environment variable is required")
    return key


def get_client(use_new_api: bool = False) -> httpx.AsyncClient:
    """Create configured httpx client for Notion API."""
    api_version = NOTION_API_VERSION_NEW if use_new_api else NOTION_API_VERSION
    return httpx.AsyncClient(
        base_url=NOTION_BASE_URL,
        headers={
            "Authorization": f"Bearer {get_api_key()}",
            "Notion-Version": api_version,
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def truncate_text(text: str, max_size: int = MAX_TEXT_SIZE) -> str:
    """Truncate text to prevent overwhelming responses."""
    if not text or len(text) <= max_size:
        return text
    return text[:max_size] + f"\n\n[... truncated, showing {max_size:,} of {len(text):,} chars]"


def extract_plain_text(rich_text: list[dict]) -> str:
    """Extract plain text from Notion rich text array."""
    return "".join(item.get("plain_text", "") for item in rich_text)


def format_property_value(prop: dict) -> Any:
    """Format a Notion property value for display."""
    prop_type = prop.get("type")

    # Simple direct value types
    if prop_type in ("number", "checkbox", "url", "email", "phone_number", "created_time", "last_edited_time"):
        return prop.get(prop_type)

    # Rich text types
    if prop_type in ("title", "rich_text"):
        return extract_plain_text(prop.get(prop_type, []))

    # Single select types (select, status)
    if prop_type in ("select", "status"):
        value = prop.get(prop_type)
        return value.get("name") if value else None

    # Multi-value types
    if prop_type == "multi_select":
        return [item.get("name") for item in prop.get("multi_select", [])]
    if prop_type == "people":
        return [p.get("name", p.get("id")) for p in prop.get("people", [])]
    if prop_type == "relation":
        return [r.get("id") for r in prop.get("relation", [])]

    # Date with range support
    if prop_type == "date":
        date = prop.get("date")
        if not date:
            return None
        start = date.get("start", "")
        end = date.get("end")
        return f"{start} - {end}" if end else start

    # Computed types (formula, rollup)
    if prop_type in ("formula", "rollup"):
        computed = prop.get(prop_type, {})
        return computed.get(computed.get("type"))

    # User reference types
    if prop_type in ("created_by", "last_edited_by"):
        user = prop.get(prop_type, {})
        return user.get("name", user.get("id"))

    return prop


def format_page_properties(properties: dict) -> dict:
    """Format all properties of a page for display."""
    return {name: format_property_value(prop) for name, prop in properties.items()}


def format_user(user: dict) -> dict:
    """Format a Notion user for display."""
    return {
        "id": user.get("id"),
        "type": user.get("type"),
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
        "email": user.get("person", {}).get("email") if user.get("type") == "person" else None
    }


def format_block(block: dict) -> dict:
    """Format a Notion block for readable display."""
    block_type = block.get("type", "unknown")
    formatted = {
        "id": block.get("id"),
        "type": block_type,
    }

    # Extract content based on block type
    block_data = block.get(block_type, {})

    # Text-based blocks (paragraph, headings, lists, quotes, callouts)
    if block_type in (
        "paragraph", "heading_1", "heading_2", "heading_3",
        "bulleted_list_item", "numbered_list_item", "quote", "callout"
    ):
        formatted["content"] = extract_plain_text(block_data.get("rich_text", []))
        if block_type == "callout":
            icon = block_data.get("icon", {})
            if icon.get("type") == "emoji":
                formatted["icon"] = icon.get("emoji")

    # To-do items
    elif block_type == "to_do":
        formatted["content"] = extract_plain_text(block_data.get("rich_text", []))
        formatted["checked"] = block_data.get("checked", False)

    # Toggle blocks
    elif block_type == "toggle":
        formatted["content"] = extract_plain_text(block_data.get("rich_text", []))

    # Code blocks
    elif block_type == "code":
        formatted["content"] = extract_plain_text(block_data.get("rich_text", []))
        formatted["language"] = block_data.get("language", "plain text")

    # Bookmark/embed/link blocks
    elif block_type in ("bookmark", "embed", "link_preview"):
        formatted["url"] = block_data.get("url")

    # Image/file/video/pdf blocks
    elif block_type in ("image", "file", "video", "pdf"):
        file_data = block_data.get(block_data.get("type", ""), {})
        formatted["url"] = file_data.get("url") or block_data.get("external", {}).get("url")
        caption = block_data.get("caption", [])
        if caption:
            formatted["caption"] = extract_plain_text(caption)

    # Table blocks
    elif block_type == "table":
        formatted["table_width"] = block_data.get("table_width")
        formatted["has_column_header"] = block_data.get("has_column_header")
        formatted["has_row_header"] = block_data.get("has_row_header")

    # Table row blocks
    elif block_type == "table_row":
        cells = block_data.get("cells", [])
        formatted["cells"] = [extract_plain_text(cell) for cell in cells]

    # Divider, table_of_contents, breadcrumb - no content needed
    elif block_type in ("divider", "table_of_contents", "breadcrumb"):
        pass  # type is enough

    # Child page/database references
    elif block_type == "child_page":
        formatted["title"] = block_data.get("title")
    elif block_type == "child_database":
        formatted["title"] = block_data.get("title")

    # Synced block
    elif block_type == "synced_block":
        synced_from = block_data.get("synced_from")
        if synced_from:
            formatted["synced_from"] = synced_from.get("block_id")

    # Equation block
    elif block_type == "equation":
        formatted["expression"] = block_data.get("expression")

    # Add has_children flag if true (for nested content)
    if block.get("has_children"):
        formatted["has_children"] = True

    return formatted


# Initialize MCP server
server = Server("notion")


# Define available tools
TOOLS = [
    # Data Source Query Tool (the key feature!)
    Tool(
        name="notion_query_data_source",
        description="""Query a Notion data source with filters, sorts, and pagination.

This is the key tool that provides structured querying not available in other Notion integrations.

Use notion_get_database first to get the data_source_id for your database.

Filter operators by property type:
- Text: equals, does_not_equal, contains, does_not_contain, starts_with, ends_with, is_empty, is_not_empty
- Number: equals, does_not_equal, greater_than, greater_than_or_equal_to, less_than, less_than_or_equal_to
- Select/Status: equals, does_not_equal, is_empty, is_not_empty
- Multi-select: contains, does_not_contain, is_empty, is_not_empty
- Date: equals, before, after, on_or_before, on_or_after, this_week, past_week, past_month, next_week, next_month
- Checkbox: equals, does_not_equal
- Relation/People: contains, does_not_contain, is_empty, is_not_empty""",
        inputSchema={
            "type": "object",
            "properties": {
                "data_source_id": {
                    "type": "string",
                    "description": "The ID of the data source/collection to query (UUID format)"
                },
                "filter": {
                    "type": "object",
                    "description": "Filter object following Notion's filter syntax"
                },
                "sorts": {
                    "type": "array",
                    "description": "Array of sort objects",
                    "items": {
                        "type": "object",
                        "properties": {
                            "property": {"type": "string"},
                            "direction": {"type": "string", "enum": ["ascending", "descending"]}
                        }
                    }
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results per page (max 100, default 100)",
                    "default": 100,
                    "maximum": 100
                },
                "start_cursor": {
                    "type": "string",
                    "description": "Pagination cursor from previous query"
                }
            },
            "required": ["data_source_id"]
        }
    ),

    # Get Database Schema
    Tool(
        name="notion_get_database",
        description="Get database metadata including title, description, property schema, and data source IDs. Use this to understand the structure before querying.",
        inputSchema={
            "type": "object",
            "properties": {
                "database_id": {
                    "type": "string",
                    "description": "The ID of the database (UUID format)"
                }
            },
            "required": ["database_id"]
        }
    ),

    # Search
    Tool(
        name="notion_search",
        description="Search across all pages and databases in the workspace. Returns titles and basic metadata.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                },
                "filter": {
                    "type": "object",
                    "description": "Filter by object type",
                    "properties": {
                        "property": {"type": "string", "enum": ["object"]},
                        "value": {"type": "string", "enum": ["page", "database"]}
                    }
                },
                "sort": {
                    "type": "object",
                    "description": "Sort results",
                    "properties": {
                        "direction": {"type": "string", "enum": ["ascending", "descending"]},
                        "timestamp": {"type": "string", "enum": ["last_edited_time"]}
                    }
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results (max 100)",
                    "default": 100
                },
                "start_cursor": {
                    "type": "string",
                    "description": "Pagination cursor"
                }
            },
            "required": ["query"]
        }
    ),

    # Get Page
    Tool(
        name="notion_get_page",
        description="Retrieve a page's properties by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The ID of the page (UUID format)"
                }
            },
            "required": ["page_id"]
        }
    ),

    # Get Page Content (Blocks)
    Tool(
        name="notion_get_page_content",
        description="Get the content blocks of a page (paragraphs, headings, lists, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The ID of the page"
                },
                "fetch_all": {
                    "type": "boolean",
                    "description": "Fetch all content including nested blocks (default: true). Set to false for paginated access.",
                    "default": True
                },
                "start_cursor": {
                    "type": "string",
                    "description": "Pagination cursor (only used when fetch_all is false)"
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of blocks per request (max 100)",
                    "default": 100
                }
            },
            "required": ["page_id"]
        }
    ),

    # Create Page
    Tool(
        name="notion_create_page",
        description="Create a new page in a database or as a child of another page.",
        inputSchema={
            "type": "object",
            "properties": {
                "parent": {
                    "type": "object",
                    "description": "Parent location. Use {\"data_source_id\": \"...\"} for multi-data-source databases (get ID from notion_get_database), {\"database_id\": \"...\"} for single-source databases, or {\"page_id\": \"...\"} for nested pages."
                },
                "properties": {
                    "type": "object",
                    "description": "Page properties. For database pages, use property names from the schema. Title property example: {\"Name\": {\"title\": [{\"text\": {\"content\": \"My Page\"}}]}}"
                },
                "children": {
                    "type": "array",
                    "description": "Optional content blocks to add to the page",
                    "items": {"type": "object"}
                }
            },
            "required": ["parent", "properties"]
        }
    ),

    # Update Page
    Tool(
        name="notion_update_page",
        description="Update a page's properties.",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The ID of the page to update"
                },
                "properties": {
                    "type": "object",
                    "description": "Properties to update"
                },
                "archived": {
                    "type": "boolean",
                    "description": "Set to true to archive (delete) the page"
                }
            },
            "required": ["page_id"]
        }
    ),

    # Append Blocks
    Tool(
        name="notion_append_blocks",
        description="Append content blocks to a page or block.",
        inputSchema={
            "type": "object",
            "properties": {
                "block_id": {
                    "type": "string",
                    "description": "The ID of the page or block to append to"
                },
                "children": {
                    "type": "array",
                    "description": "Array of block objects to append",
                    "items": {"type": "object"}
                }
            },
            "required": ["block_id", "children"]
        }
    ),

    # Update Block
    Tool(
        name="notion_update_block",
        description="Update a block's content.",
        inputSchema={
            "type": "object",
            "properties": {
                "block_id": {
                    "type": "string",
                    "description": "The ID of the block to update"
                },
                "block_content": {
                    "type": "object",
                    "description": "The block type and content to update. Example: {\"paragraph\": {\"rich_text\": [{\"text\": {\"content\": \"Updated text\"}}]}}"
                },
                "archived": {
                    "type": "boolean",
                    "description": "Set to true to archive (delete) the block"
                }
            },
            "required": ["block_id"]
        }
    ),

    # List Users
    Tool(
        name="notion_list_users",
        description="List all users in the workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "start_cursor": {
                    "type": "string",
                    "description": "Pagination cursor"
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of users to return (max 100)",
                    "default": 100
                }
            }
        }
    ),

    # Get User
    Tool(
        name="notion_get_user",
        description="Get details about a specific user.",
        inputSchema={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user"
                }
            },
            "required": ["user_id"]
        }
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        # Use new API version for database/data source operations
        use_new_api = name in ("notion_get_database", "notion_query_data_source", "notion_create_page")

        async with get_client(use_new_api=use_new_api) as client:
            if name == "notion_query_data_source":
                result = await query_data_source(client, arguments)
            elif name == "notion_get_database":
                result = await get_database(client, arguments)
            elif name == "notion_search":
                result = await search(client, arguments)
            elif name == "notion_get_page":
                result = await get_page(client, arguments)
            elif name == "notion_get_page_content":
                result = await get_page_content(client, arguments)
            elif name == "notion_create_page":
                result = await create_page(client, arguments)
            elif name == "notion_update_page":
                result = await update_page(client, arguments)
            elif name == "notion_append_blocks":
                result = await append_blocks(client, arguments)
            elif name == "notion_update_block":
                result = await update_block(client, arguments)
            elif name == "notion_list_users":
                result = await list_users(client, arguments)
            elif name == "notion_get_user":
                result = await get_user(client, arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}

        text = json.dumps(result, indent=2, default=str)
        return [TextContent(type="text", text=truncate_text(text))]

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        return [TextContent(
            type="text",
            text=f"Notion API Error {e.response.status_code}: {error_body}"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {str(e)}")]


# Tool implementations

async def query_data_source(client: httpx.AsyncClient, args: dict) -> dict:
    """Query a Notion data source with filters and sorts (new API)."""
    data_source_id = args["data_source_id"].replace("-", "")

    body = {}
    if "filter" in args:
        body["filter"] = args["filter"]
    if "sorts" in args:
        body["sorts"] = args["sorts"]
    if "page_size" in args:
        body["page_size"] = min(args["page_size"], 100)
    if "start_cursor" in args:
        body["start_cursor"] = args["start_cursor"]

    response = await client.post(f"/data_sources/{data_source_id}/query", json=body)
    response.raise_for_status()
    data = response.json()

    # Format results for readability
    results = []
    for page in data.get("results", [])[:MAX_LIST_ITEMS]:
        formatted = {
            "id": page["id"],
            "url": page.get("url"),
            "created_time": page.get("created_time"),
            "last_edited_time": page.get("last_edited_time"),
            "properties": format_page_properties(page.get("properties", {}))
        }
        results.append(formatted)

    return {
        "results": results,
        "has_more": data.get("has_more", False),
        "next_cursor": data.get("next_cursor"),
        "result_count": len(results)
    }


async def get_database(client: httpx.AsyncClient, args: dict) -> dict:
    """Get database metadata and schema."""
    database_id = args["database_id"].replace("-", "")

    response = await client.get(f"/databases/{database_id}")
    response.raise_for_status()
    data = response.json()

    # Extract data sources (for multi-source databases)
    data_sources = [
        {"id": ds.get("id"), "name": ds.get("name")}
        for ds in data.get("data_sources", [])
    ]

    # Extract property schema
    properties_schema = {}
    for name, prop in data.get("properties", {}).items():
        prop_type = prop.get("type")
        prop_info = {"type": prop_type, "id": prop.get("id")}

        # Add options for select-like types
        if prop_type in ("select", "multi_select", "status"):
            type_data = prop.get(prop_type, {})
            prop_info["options"] = [opt["name"] for opt in type_data.get("options", [])]
            if prop_type == "status":
                prop_info["groups"] = [g["name"] for g in type_data.get("groups", [])]
        elif prop_type == "relation":
            prop_info["database_id"] = prop.get("relation", {}).get("database_id")

        properties_schema[name] = prop_info

    result = {
        "id": data["id"],
        "title": extract_plain_text(data.get("title", [])),
        "description": extract_plain_text(data.get("description", [])),
        "url": data.get("url"),
        "created_time": data.get("created_time"),
        "last_edited_time": data.get("last_edited_time"),
        "properties": properties_schema
    }

    # Include data sources if present
    if data_sources:
        result["data_sources"] = data_sources
        result["note"] = "This database has multiple data sources. Use notion_query_data_source with a data_source_id to query."

    return result


async def search(client: httpx.AsyncClient, args: dict) -> dict:
    """Search across workspace."""
    body = {"query": args["query"]}

    if "filter" in args:
        body["filter"] = args["filter"]
    if "sort" in args:
        body["sort"] = args["sort"]
    if "page_size" in args:
        body["page_size"] = min(args["page_size"], 100)
    if "start_cursor" in args:
        body["start_cursor"] = args["start_cursor"]

    response = await client.post("/search", json=body)
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("results", [])[:MAX_LIST_ITEMS]:
        obj_type = item.get("object")
        formatted = {
            "id": item["id"],
            "type": obj_type,
            "url": item.get("url"),
            "created_time": item.get("created_time"),
            "last_edited_time": item.get("last_edited_time"),
        }

        if obj_type == "page":
            formatted["properties"] = format_page_properties(item.get("properties", {}))
        elif obj_type == "database":
            formatted["title"] = extract_plain_text(item.get("title", []))

        results.append(formatted)

    return {
        "results": results,
        "has_more": data.get("has_more", False),
        "next_cursor": data.get("next_cursor"),
        "result_count": len(results)
    }


async def get_page(client: httpx.AsyncClient, args: dict) -> dict:
    """Get a page's properties."""
    page_id = args["page_id"].replace("-", "")

    response = await client.get(f"/pages/{page_id}")
    response.raise_for_status()
    data = response.json()

    return {
        "id": data["id"],
        "url": data.get("url"),
        "created_time": data.get("created_time"),
        "last_edited_time": data.get("last_edited_time"),
        "created_by": data.get("created_by", {}).get("id"),
        "last_edited_by": data.get("last_edited_by", {}).get("id"),
        "parent": data.get("parent"),
        "archived": data.get("archived"),
        "properties": format_page_properties(data.get("properties", {}))
    }


async def get_page_content(client: httpx.AsyncClient, args: dict) -> dict:
    """Get content blocks of a page."""
    page_id = args["page_id"].replace("-", "")
    fetch_all = args.get("fetch_all", True)
    page_size = min(args.get("page_size", 100), 100)

    async def fetch_blocks(block_id: str, cursor: str | None = None) -> list[dict]:
        """Fetch blocks for a given parent, handling pagination."""
        all_blocks = []
        params = {"page_size": page_size}
        if cursor:
            params["start_cursor"] = cursor

        while True:
            response = await client.get(f"/blocks/{block_id}/children", params=params)
            response.raise_for_status()
            data = response.json()

            for block in data.get("results", []):
                formatted = format_block(block)
                # Recursively fetch children if fetch_all and has_children
                if fetch_all and block.get("has_children"):
                    formatted["children"] = await fetch_blocks(block["id"])
                all_blocks.append(formatted)

            if not fetch_all or not data.get("has_more"):
                break
            params["start_cursor"] = data.get("next_cursor")

        return all_blocks

    if fetch_all:
        # Fetch everything including nested blocks
        blocks = await fetch_blocks(page_id)
        return {"blocks": blocks}
    else:
        # Single page fetch for manual pagination
        params = {"page_size": page_size}
        if "start_cursor" in args:
            params["start_cursor"] = args["start_cursor"]

        response = await client.get(f"/blocks/{page_id}/children", params=params)
        response.raise_for_status()
        data = response.json()

        blocks = [format_block(block) for block in data.get("results", [])]
        return {
            "blocks": blocks,
            "has_more": data.get("has_more", False),
            "next_cursor": data.get("next_cursor")
        }


async def create_page(client: httpx.AsyncClient, args: dict) -> dict:
    """Create a new page."""
    body = {
        "parent": args["parent"],
        "properties": args["properties"]
    }
    if "children" in args:
        body["children"] = args["children"]

    response = await client.post("/pages", json=body)
    response.raise_for_status()
    data = response.json()

    return {
        "id": data["id"],
        "url": data.get("url"),
        "created_time": data.get("created_time"),
        "properties": format_page_properties(data.get("properties", {}))
    }


async def update_page(client: httpx.AsyncClient, args: dict) -> dict:
    """Update a page's properties."""
    page_id = args["page_id"].replace("-", "")

    body = {}
    if "properties" in args:
        body["properties"] = args["properties"]
    if "archived" in args:
        body["archived"] = args["archived"]

    response = await client.patch(f"/pages/{page_id}", json=body)
    response.raise_for_status()
    data = response.json()

    return {
        "id": data["id"],
        "url": data.get("url"),
        "last_edited_time": data.get("last_edited_time"),
        "properties": format_page_properties(data.get("properties", {}))
    }


async def append_blocks(client: httpx.AsyncClient, args: dict) -> dict:
    """Append blocks to a page or block."""
    block_id = args["block_id"].replace("-", "")

    body = {"children": args["children"]}

    response = await client.patch(f"/blocks/{block_id}/children", json=body)
    response.raise_for_status()
    data = response.json()

    return {
        "results": data.get("results", []),
        "block_count": len(data.get("results", []))
    }


async def update_block(client: httpx.AsyncClient, args: dict) -> dict:
    """Update a block."""
    block_id = args["block_id"].replace("-", "")

    body = {}
    if "block_content" in args:
        body.update(args["block_content"])
    if "archived" in args:
        body["archived"] = args["archived"]

    response = await client.patch(f"/blocks/{block_id}", json=body)
    response.raise_for_status()
    data = response.json()

    return {
        "id": data["id"],
        "type": data.get("type"),
        "last_edited_time": data.get("last_edited_time")
    }


async def list_users(client: httpx.AsyncClient, args: dict) -> dict:
    """List workspace users."""
    params = {}
    if "start_cursor" in args:
        params["start_cursor"] = args["start_cursor"]
    if "page_size" in args:
        params["page_size"] = min(args["page_size"], 100)

    response = await client.get("/users", params=params)
    response.raise_for_status()
    data = response.json()

    return {
        "users": [format_user(u) for u in data.get("results", [])[:MAX_LIST_ITEMS]],
        "has_more": data.get("has_more", False),
        "next_cursor": data.get("next_cursor")
    }


async def get_user(client: httpx.AsyncClient, args: dict) -> dict:
    """Get a specific user."""
    user_id = args["user_id"].replace("-", "")
    response = await client.get(f"/users/{user_id}")
    response.raise_for_status()
    return format_user(response.json())


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
