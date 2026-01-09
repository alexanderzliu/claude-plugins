#!/usr/bin/env python3
"""
Databricks MCP Server

Provides tools for Claude Code to interact with Databricks:
- Run notebooks and monitor cell outputs
- Read/write notebook files
- Create and run jobs
- Monitor job logs
"""

import asyncio
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import (
    RunLifeCycleState,
    RunResultState,
    NotebookTask,
    Task,
    JobEnvironment,
)
from databricks.sdk.service.compute import Environment

# Initialize the MCP server
server = Server("databricks")

# ============================================================================
# Truncation Utilities
# ============================================================================

# Size limits to prevent overwhelming Claude Code while maximizing useful context
MAX_TEXT_SIZE = 100_000      # ~100KB per text field
MAX_CELL_CONTENT = 50_000    # Per notebook cell
MAX_LIST_ITEMS = 100         # For unbounded list operations
MAX_LOG_SIZE = 80_000        # Logs can be verbose


def truncate_text(
    text: str,
    max_size: int = MAX_TEXT_SIZE,
    field_name: str = "content"
) -> tuple[str, dict]:
    """
    Truncate text if it exceeds max_size.

    Returns:
        (text, metadata) - metadata is empty dict if no truncation occurred,
        otherwise contains truncation info for the agent.
    """
    if not text or len(text) <= max_size:
        return text, {}

    truncated = text[:max_size]
    metadata = {
        f"{field_name}_truncated": True,
        f"{field_name}_total_size": len(text),
        f"{field_name}_shown_size": max_size,
    }
    suffix = f"\n\n[... truncated, showing {max_size:,} of {len(text):,} chars]"
    return truncated + suffix, metadata

# Initialize Databricks client (uses DATABRICKS_HOST and DATABRICKS_TOKEN env vars)
def get_client() -> WorkspaceClient:
    """Get Databricks workspace client."""
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")

    if not host or not token:
        raise ValueError("DATABRICKS_HOST and DATABRICKS_TOKEN environment variables must be set")

    return WorkspaceClient(host=host, token=token)


# ============================================================================
# Tool Definitions
# ============================================================================

TOOLS = [
    # Notebook tools
    Tool(
        name="databricks_run_notebook",
        description="Run a Databricks notebook using serverless compute and return a run_id. Use databricks_get_run_output to get results.",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Workspace path to the notebook (e.g., /Workspace/Users/user@example.com/my_notebook)"
                },
                "parameters": {
                    "type": "object",
                    "description": "Notebook widget parameters as key-value pairs",
                    "additionalProperties": {"type": "string"}
                },
                "timeout_minutes": {
                    "type": "integer",
                    "description": "Timeout in minutes (default: 30)",
                    "default": 30
                }
            },
            "required": ["notebook_path"]
        }
    ),
    Tool(
        name="databricks_get_run_output",
        description="Get the output of a notebook run, including cell-by-cell results. Use after databricks_run_notebook.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "integer",
                    "description": "The run ID returned by databricks_run_notebook"
                }
            },
            "required": ["run_id"]
        }
    ),
    Tool(
        name="databricks_wait_for_run",
        description="Wait for a notebook or job run to complete, polling until done.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "integer",
                    "description": "The run ID to wait for"
                },
                "timeout_minutes": {
                    "type": "integer",
                    "description": "Maximum time to wait in minutes (default: 30)",
                    "default": 30
                },
                "poll_interval_seconds": {
                    "type": "integer",
                    "description": "Seconds between status checks (default: 10)",
                    "default": 10
                }
            },
            "required": ["run_id"]
        }
    ),
    Tool(
        name="databricks_read_notebook",
        description="Read the contents of a Databricks notebook (.py file with # COMMAND separators). Supports pagination for large notebooks.",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Workspace path to the notebook"
                },
                "cell_offset": {
                    "type": "integer",
                    "description": "Start reading from this cell index (0-based, default: 0)",
                    "default": 0
                },
                "cell_limit": {
                    "type": "integer",
                    "description": "Maximum number of cells to return (default: all cells)"
                }
            },
            "required": ["notebook_path"]
        }
    ),
    Tool(
        name="databricks_write_notebook",
        description="Write/update a Databricks notebook (.py file with # COMMAND separators).",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Workspace path to the notebook"
                },
                "content": {
                    "type": "string",
                    "description": "Notebook content (Python with # COMMAND separators)"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite existing notebook (default: true)",
                    "default": True
                }
            },
            "required": ["notebook_path", "content"]
        }
    ),
    Tool(
        name="databricks_list_notebooks",
        description="List notebooks in a workspace directory. Returns up to 100 items by default with pagination support.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Workspace directory path to list"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum items to return (default: 100)",
                    "default": 100
                },
                "offset": {
                    "type": "integer",
                    "description": "Skip this many items (for pagination, default: 0)",
                    "default": 0
                }
            },
            "required": ["path"]
        }
    ),
    Tool(
        name="databricks_update_notebook_cell",
        description="Update specific cell(s) in a Databricks notebook without rewriting the entire content. More efficient than databricks_write_notebook when making targeted changes.",
        inputSchema={
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Workspace path to the notebook"
                },
                "cell_index": {
                    "type": "integer",
                    "description": "0-based index of the cell to update (use this OR updates, not both)"
                },
                "new_content": {
                    "type": "string",
                    "description": "New content for the cell (required if cell_index is provided)"
                },
                "updates": {
                    "type": "array",
                    "description": "Array of cell updates for batch operations (use this OR cell_index, not both)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {
                                "type": "integer",
                                "description": "0-based cell index"
                            },
                            "content": {
                                "type": "string",
                                "description": "New content for this cell"
                            }
                        },
                        "required": ["index", "content"]
                    }
                }
            },
            "required": ["notebook_path"]
        }
    ),

    # Job tools
    Tool(
        name="databricks_create_job",
        description="Create a Databricks job with notebook tasks using serverless compute.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Job name"
                },
                "tasks": {
                    "type": "array",
                    "description": "List of notebook tasks",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_key": {
                                "type": "string",
                                "description": "Unique task identifier"
                            },
                            "notebook_path": {
                                "type": "string",
                                "description": "Workspace path to the notebook"
                            },
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of task_keys this task depends on"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Notebook parameters",
                                "additionalProperties": {"type": "string"}
                            }
                        },
                        "required": ["task_key", "notebook_path"]
                    }
                }
            },
            "required": ["name", "tasks"]
        }
    ),
    Tool(
        name="databricks_run_job",
        description="Trigger a job run by job ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "integer",
                    "description": "The job ID to run"
                },
                "parameters": {
                    "type": "object",
                    "description": "Job parameters to override",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["job_id"]
        }
    ),
    Tool(
        name="databricks_get_job_run_status",
        description="Get the status and task states of a job run.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "integer",
                    "description": "The run ID to check"
                }
            },
            "required": ["run_id"]
        }
    ),
    Tool(
        name="databricks_get_run_logs",
        description="Get stdout/stderr logs from a run. Supports offset for reading large logs in chunks.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "integer",
                    "description": "The run ID to get logs for"
                },
                "offset": {
                    "type": "integer",
                    "description": "Character offset to start reading from (default: 0)",
                    "default": 0
                },
                "max_size": {
                    "type": "integer",
                    "description": "Maximum characters to return (default: 80000)",
                    "default": 80000
                }
            },
            "required": ["run_id"]
        }
    ),
    Tool(
        name="databricks_list_jobs",
        description="List jobs in the workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "name_filter": {
                    "type": "string",
                    "description": "Filter jobs by name (substring match)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of jobs to return (default: 25)",
                    "default": 25
                }
            }
        }
    ),
    Tool(
        name="databricks_cancel_run",
        description="Cancel a running job or notebook run.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "integer",
                    "description": "The run ID to cancel"
                }
            },
            "required": ["run_id"]
        }
    ),

    # Cluster tools
    Tool(
        name="databricks_list_clusters",
        description="List clusters in the workspace. Returns max 25 clusters by default to avoid large payloads.",
        inputSchema={
            "type": "object",
            "properties": {
                "filter_by": {
                    "type": "string",
                    "enum": ["all", "running", "terminated"],
                    "description": "Filter clusters by state (default: all)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max clusters to return (default: 25, max: 100)",
                    "default": 25
                }
            }
        }
    ),
    Tool(
        name="databricks_get_cluster_status",
        description="Get detailed status and information about a specific cluster.",
        inputSchema={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The cluster ID to check"
                }
            },
            "required": ["cluster_id"]
        }
    ),
    Tool(
        name="databricks_start_cluster",
        description="Start a terminated cluster and wait until running.",
        inputSchema={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The cluster ID to start"
                },
                "wait": {
                    "type": "boolean",
                    "description": "Wait for cluster to be running (default: true)",
                    "default": True
                },
                "timeout_minutes": {
                    "type": "integer",
                    "description": "Maximum time to wait in minutes (default: 20)",
                    "default": 20
                }
            },
            "required": ["cluster_id"]
        }
    ),
    Tool(
        name="databricks_stop_cluster",
        description="Stop/terminate a running cluster.",
        inputSchema={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The cluster ID to stop"
                }
            },
            "required": ["cluster_id"]
        }
    ),
    Tool(
        name="databricks_create_cluster",
        description="Create a new cluster with Unity Catalog enabled. Defaults: Spark 17.3 LTS, m5.xlarge nodes, 120min auto-terminate, SINGLE_USER access mode.",
        inputSchema={
            "type": "object",
            "properties": {
                "cluster_name": {
                    "type": "string",
                    "description": "Name for the cluster"
                },
                "num_workers": {
                    "type": "integer",
                    "description": "Number of worker nodes (default: 1, use 0 for single-node)",
                    "default": 1
                },
                "node_type_id": {
                    "type": "string",
                    "description": "Node type (default: m5.xlarge, use larger for complex workloads)",
                    "default": "m5.xlarge"
                },
                "spark_version": {
                    "type": "string",
                    "description": "Spark runtime version (default: 17.3.x-scala2.12)"
                },
                "policy_id": {
                    "type": "string",
                    "description": "Cluster policy ID (optional, use if your organization requires a specific policy)"
                },
                "data_security_mode": {
                    "type": "string",
                    "description": "Access mode for Unity Catalog. SINGLE_USER (default): single user only. USER_ISOLATION: shared with isolation. NONE: no Unity Catalog.",
                    "enum": ["SINGLE_USER", "USER_ISOLATION", "NONE"],
                    "default": "SINGLE_USER"
                },
                "single_user_name": {
                    "type": "string",
                    "description": "User email for SINGLE_USER mode. Defaults to the authenticated user."
                },
                "autotermination_minutes": {
                    "type": "integer",
                    "description": "Auto-terminate after idle minutes (default: 120)",
                    "default": 120
                },
                "custom_tags": {
                    "type": "object",
                    "description": "Custom tags for the cluster (optional key-value pairs)",
                    "additionalProperties": {"type": "string"}
                },
                "wait": {
                    "type": "boolean",
                    "description": "Wait for cluster to be running (default: false)",
                    "default": False
                },
                "timeout_minutes": {
                    "type": "integer",
                    "description": "Max wait time if wait=true (default: 20)",
                    "default": 20
                }
            },
            "required": ["cluster_name"]
        }
    ),
    Tool(
        name="databricks_list_cluster_policies",
        description="List available cluster policies to find policy_id for cluster creation.",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),

    # Interactive execution tools
    Tool(
        name="databricks_create_context",
        description="Create an execution context on a running cluster for interactive code execution. Returns a context_id for use with databricks_execute_cell.",
        inputSchema={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The running cluster ID"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "scala", "sql", "r"],
                    "description": "Programming language for the context (default: python)"
                }
            },
            "required": ["cluster_id"]
        }
    ),
    Tool(
        name="databricks_execute_cell",
        description="Execute code in an execution context and get the output. Variables and state persist between calls.",
        inputSchema={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The cluster ID"
                },
                "context_id": {
                    "type": "string",
                    "description": "The execution context ID from databricks_create_context"
                },
                "code": {
                    "type": "string",
                    "description": "The code to execute"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "scala", "sql", "r"],
                    "description": "Programming language (default: python)"
                },
                "timeout_minutes": {
                    "type": "integer",
                    "description": "Maximum execution time in minutes (default: 30)",
                    "default": 30
                }
            },
            "required": ["cluster_id", "context_id", "code"]
        }
    ),
    Tool(
        name="databricks_destroy_context",
        description="Destroy an execution context when done with interactive execution.",
        inputSchema={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The cluster ID"
                },
                "context_id": {
                    "type": "string",
                    "description": "The execution context ID to destroy"
                }
            },
            "required": ["cluster_id", "context_id"]
        }
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return TOOLS


# ============================================================================
# Tool Implementations
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    try:
        client = get_client()

        # Notebook tools
        if name == "databricks_run_notebook":
            result = await run_notebook(client, arguments)
        elif name == "databricks_get_run_output":
            result = await get_run_output(client, arguments)
        elif name == "databricks_wait_for_run":
            result = await wait_for_run(client, arguments)
        elif name == "databricks_read_notebook":
            result = await read_notebook(client, arguments)
        elif name == "databricks_write_notebook":
            result = await write_notebook(client, arguments)
        elif name == "databricks_list_notebooks":
            result = await list_notebooks(client, arguments)
        elif name == "databricks_update_notebook_cell":
            result = await update_notebook_cell(client, arguments)

        # Job tools
        elif name == "databricks_create_job":
            result = await create_job(client, arguments)
        elif name == "databricks_run_job":
            result = await run_job(client, arguments)
        elif name == "databricks_get_job_run_status":
            result = await get_job_run_status(client, arguments)
        elif name == "databricks_get_run_logs":
            result = await get_run_logs(client, arguments)
        elif name == "databricks_list_jobs":
            result = await list_jobs(client, arguments)
        elif name == "databricks_cancel_run":
            result = await cancel_run(client, arguments)

        # Cluster tools
        elif name == "databricks_list_clusters":
            result = await list_clusters(client, arguments)
        elif name == "databricks_get_cluster_status":
            result = await get_cluster_status(client, arguments)
        elif name == "databricks_start_cluster":
            result = await start_cluster(client, arguments)
        elif name == "databricks_stop_cluster":
            result = await stop_cluster(client, arguments)
        elif name == "databricks_create_cluster":
            result = await create_cluster(client, arguments)
        elif name == "databricks_list_cluster_policies":
            result = await list_cluster_policies(client, arguments)

        # Interactive execution tools
        elif name == "databricks_create_context":
            result = await create_context(client, arguments)
        elif name == "databricks_execute_cell":
            result = await execute_cell(client, arguments)
        elif name == "databricks_destroy_context":
            result = await destroy_context(client, arguments)

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=str(result))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {str(e)}")]


# ============================================================================
# Notebook Tool Implementations
# ============================================================================

async def run_notebook(client: WorkspaceClient, args: dict) -> dict:
    """Run a notebook using serverless compute."""
    notebook_path = args["notebook_path"]
    parameters = args.get("parameters", {})
    timeout_minutes = args.get("timeout_minutes", 30)

    # Use serverless compute with environment version
    # Environment version "2" is the current serverless Python environment
    environment_key = "serverless_env"
    run = client.jobs.submit(
        run_name=f"Claude Code: {notebook_path.split('/')[-1]}",
        tasks=[
            Task(
                task_key="notebook_task",
                notebook_task=NotebookTask(
                    notebook_path=notebook_path,
                    base_parameters=parameters
                ),
                environment_key=environment_key,
                timeout_seconds=timeout_minutes * 60
            )
        ],
        environments=[
            JobEnvironment(
                environment_key=environment_key,
                spec=Environment(environment_version="2")
            )
        ]
    )

    return {
        "run_id": run.run_id,
        "message": f"Notebook run submitted. Use databricks_wait_for_run or databricks_get_run_output with run_id={run.run_id}"
    }


async def get_run_output(client: WorkspaceClient, args: dict) -> dict:
    """Get the output of a run including notebook cell outputs."""
    run_id = args["run_id"]

    # Get run details
    run = client.jobs.get_run(run_id=run_id)

    # Get run output
    output = client.jobs.get_run_output(run_id=run_id)

    result = {
        "run_id": run_id,
        "state": run.state.life_cycle_state.value if run.state else "UNKNOWN",
        "result_state": run.state.result_state.value if run.state and run.state.result_state else None,
        "state_message": run.state.state_message if run.state else None,
    }

    # Parse notebook output if available (with truncation)
    if output.notebook_output:
        nb_result = output.notebook_output.result
        if nb_result:
            nb_result, nb_meta = truncate_text(nb_result, MAX_TEXT_SIZE, "notebook_result")
            result.update(nb_meta)

        result["notebook_output"] = {
            "result": nb_result,
            "truncated": output.notebook_output.truncated
        }

    # Include error info if present (with truncation for trace)
    if output.error:
        result["error"] = output.error

    if output.error_trace:
        error_trace, trace_meta = truncate_text(output.error_trace, MAX_TEXT_SIZE, "error_trace")
        result["error_trace"] = error_trace
        result.update(trace_meta)

    # Include logs if available (with truncation)
    if output.logs:
        logs, logs_meta = truncate_text(output.logs, MAX_LOG_SIZE, "logs")
        result["logs"] = logs
        result.update(logs_meta)

    return result


async def wait_for_run(client: WorkspaceClient, args: dict) -> dict:
    """Wait for a run to complete."""
    run_id = args["run_id"]
    timeout_minutes = args.get("timeout_minutes", 30)
    poll_interval = args.get("poll_interval_seconds", 10)

    max_iterations = (timeout_minutes * 60) // poll_interval
    iteration = 0

    terminal_states = {
        RunLifeCycleState.TERMINATED,
        RunLifeCycleState.SKIPPED,
        RunLifeCycleState.INTERNAL_ERROR
    }

    while iteration < max_iterations:
        run = client.jobs.get_run(run_id=run_id)
        state = run.state

        if state and state.life_cycle_state in terminal_states:
            # Run completed, get output
            output_result = await get_run_output(client, {"run_id": run_id})
            return output_result

        iteration += 1
        await asyncio.sleep(poll_interval)

    return {
        "run_id": run_id,
        "status": "TIMEOUT",
        "message": f"Run did not complete within {timeout_minutes} minutes"
    }


async def read_notebook(client: WorkspaceClient, args: dict) -> dict:
    """Read notebook content from workspace with optional pagination."""
    import base64
    from databricks.sdk.service.workspace import ExportFormat

    notebook_path = args["notebook_path"]
    cell_offset = args.get("cell_offset", 0)
    cell_limit = args.get("cell_limit")  # None means all cells

    # Export notebook as SOURCE format (Python)
    export = client.workspace.export(path=notebook_path, format=ExportFormat.SOURCE)

    # Decode content
    content = base64.b64decode(export.content).decode("utf-8")

    # Parse cells (split by # COMMAND ----------)
    all_cells = _parse_notebook_cells(content)
    total_cells = len(all_cells)

    # Apply pagination
    if cell_limit is not None:
        cells_to_return = all_cells[cell_offset:cell_offset + cell_limit]
    else:
        cells_to_return = all_cells[cell_offset:]

    # Truncate individual cells if they're too large, with metadata
    cells_output = []
    truncation_info = {}

    for i, cell in enumerate(cells_to_return):
        actual_index = cell_offset + i
        if len(cell) > MAX_CELL_CONTENT:
            truncated_cell, _ = truncate_text(cell, MAX_CELL_CONTENT, "cell")
            cells_output.append(truncated_cell)
            truncation_info[actual_index] = {
                "truncated": True,
                "total_size": len(cell),
                "shown_size": MAX_CELL_CONTENT
            }
        else:
            cells_output.append(cell)

    result = {
        "path": notebook_path,
        "total_cells": total_cells,
        "cells_returned": len(cells_output),
        "cell_offset": cell_offset,
        "cells": cells_output,
    }

    # Include truncation info if any cells were truncated
    if truncation_info:
        result["truncated_cells"] = truncation_info
        result["truncation_note"] = "Some cells were truncated. Use cell_offset/cell_limit to read specific cells."

    # Indicate if there are more cells available
    if cell_offset + len(cells_output) < total_cells:
        result["has_more"] = True
        result["next_offset"] = cell_offset + len(cells_output)

    return result


async def write_notebook(client: WorkspaceClient, args: dict) -> dict:
    """Write notebook content to workspace."""
    import base64
    from databricks.sdk.service.workspace import ImportFormat, Language

    notebook_path = args["notebook_path"]
    content = args["content"]
    overwrite = args.get("overwrite", True)

    # Encode content
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # Import notebook
    client.workspace.import_(
        path=notebook_path,
        content=encoded_content,
        format=ImportFormat.SOURCE,
        language=Language.PYTHON,
        overwrite=overwrite
    )

    return {
        "path": notebook_path,
        "status": "success",
        "message": f"Notebook written to {notebook_path}"
    }


async def list_notebooks(client: WorkspaceClient, args: dict) -> dict:
    """List notebooks in a directory with pagination support."""
    path = args["path"]
    limit = args.get("limit", MAX_LIST_ITEMS)
    offset = args.get("offset", 0)

    items = client.workspace.list(path=path)

    # Collect all items first (API doesn't support pagination directly)
    all_items = []
    for item in items:
        all_items.append({
            "path": item.path,
            "type": item.object_type.value if item.object_type else "UNKNOWN",
            "language": item.language.value if item.language else None
        })

    total_count = len(all_items)

    # Apply pagination
    paginated_items = all_items[offset:offset + limit]

    result = {
        "path": path,
        "items": paginated_items,
        "total_count": total_count,
        "returned_count": len(paginated_items),
        "offset": offset,
    }

    # Indicate if there are more items
    if offset + len(paginated_items) < total_count:
        result["has_more"] = True
        result["next_offset"] = offset + len(paginated_items)

    return result


# Cell separator pattern used in Databricks notebooks
CELL_SEPARATOR = "# COMMAND ----------"


def _parse_notebook_cells(content: str) -> list[str]:
    """Parse notebook content into cells."""
    cells = []
    current_cell = []

    for line in content.split("\n"):
        if line.strip().startswith("# COMMAND ----------"):
            if current_cell:
                cells.append("\n".join(current_cell))
                current_cell = []
        else:
            current_cell.append(line)

    if current_cell:
        cells.append("\n".join(current_cell))

    return cells


def _reconstruct_notebook(cells: list[str]) -> str:
    """Reconstruct notebook content from cells."""
    return f"\n\n{CELL_SEPARATOR}\n\n".join(cells)


def _validate_cell_content(content: str) -> tuple[bool, str]:
    """Validate cell content doesn't contain cell separators."""
    if "# COMMAND ----------" in content or ("# COMMAND" in content and "----------" in content):
        return False, "Cell content cannot contain '# COMMAND ----------' separator - this would corrupt notebook structure"
    return True, ""


async def update_notebook_cell(client: WorkspaceClient, args: dict) -> dict:
    """Update specific cell(s) in a notebook without rewriting entire content."""
    import base64
    from databricks.sdk.service.workspace import ImportFormat, Language, ExportFormat

    notebook_path = args["notebook_path"]
    cell_index = args.get("cell_index")
    new_content = args.get("new_content")
    updates = args.get("updates")

    # Validate input combinations
    has_single = cell_index is not None
    has_batch = updates is not None

    if has_single and has_batch:
        return {
            "status": "error",
            "message": "Provide either cell_index+new_content OR updates, not both"
        }

    if not has_single and not has_batch:
        return {
            "status": "error",
            "message": "Must provide either cell_index+new_content or updates array"
        }

    if has_single and new_content is None:
        return {
            "status": "error",
            "message": "new_content is required when using cell_index"
        }

    # Read existing notebook
    export = client.workspace.export(path=notebook_path, format=ExportFormat.SOURCE)
    content = base64.b64decode(export.content).decode("utf-8")
    cells = _parse_notebook_cells(content)

    # Build updates list
    if has_single:
        updates_to_apply = [{"index": cell_index, "content": new_content}]
    else:
        updates_to_apply = updates

    # Validate all updates
    for update in updates_to_apply:
        idx = update["index"]
        cell_content = update["content"]

        # Bounds check
        if idx < 0 or idx >= len(cells):
            return {
                "status": "error",
                "message": f"Cell index {idx} out of bounds (notebook has {len(cells)} cells, indices 0-{len(cells)-1})"
            }

        # Separator injection check
        valid, error_msg = _validate_cell_content(cell_content)
        if not valid:
            return {
                "status": "error",
                "message": f"Invalid content for cell {idx}: {error_msg}"
            }

    # Apply updates
    updated_indices = []
    for update in updates_to_apply:
        idx = update["index"]
        cells[idx] = update["content"]
        updated_indices.append(idx)

    # Reconstruct and write notebook
    new_notebook_content = _reconstruct_notebook(cells)
    encoded_content = base64.b64encode(new_notebook_content.encode("utf-8")).decode("utf-8")

    client.workspace.import_(
        path=notebook_path,
        content=encoded_content,
        format=ImportFormat.SOURCE,
        language=Language.PYTHON,
        overwrite=True
    )

    return {
        "path": notebook_path,
        "status": "success",
        "updated_cells": updated_indices,
        "total_cells": len(cells),
        "message": f"Updated cell(s) {updated_indices} in {notebook_path}"
    }


# ============================================================================
# Job Tool Implementations
# ============================================================================

async def create_job(client: WorkspaceClient, args: dict) -> dict:
    """Create a job with notebook tasks using serverless compute."""
    from databricks.sdk.service.jobs import TaskDependency

    name = args["name"]
    task_configs = args["tasks"]

    # Use serverless compute with environment version
    environment_key = "serverless_env"

    # Build tasks
    tasks = []
    for tc in task_configs:
        task = Task(
            task_key=tc["task_key"],
            notebook_task=NotebookTask(
                notebook_path=tc["notebook_path"],
                base_parameters=tc.get("parameters", {})
            ),
            environment_key=environment_key
        )

        # Add dependencies if specified
        if tc.get("depends_on"):
            task.depends_on = [TaskDependency(task_key=dep) for dep in tc["depends_on"]]

        tasks.append(task)

    # Create job with serverless environment (version "2" is current)
    job = client.jobs.create(
        name=name,
        tasks=tasks,
        environments=[
            JobEnvironment(
                environment_key=environment_key,
                spec=Environment(environment_version="2")
            )
        ]
    )

    return {
        "job_id": job.job_id,
        "name": name,
        "task_count": len(tasks),
        "message": f"Job created. Use databricks_run_job with job_id={job.job_id} to run it."
    }


async def run_job(client: WorkspaceClient, args: dict) -> dict:
    """Trigger a job run."""
    job_id = args["job_id"]
    parameters = args.get("parameters")

    run = client.jobs.run_now(
        job_id=job_id,
        notebook_params=parameters
    )

    return {
        "run_id": run.run_id,
        "job_id": job_id,
        "message": f"Job run started. Use databricks_wait_for_run with run_id={run.run_id}"
    }


async def get_job_run_status(client: WorkspaceClient, args: dict) -> dict:
    """Get job run status with task details."""
    run_id = args["run_id"]

    run = client.jobs.get_run(run_id=run_id)

    result = {
        "run_id": run_id,
        "job_id": run.job_id,
        "state": run.state.life_cycle_state.value if run.state else "UNKNOWN",
        "result_state": run.state.result_state.value if run.state and run.state.result_state else None,
        "state_message": run.state.state_message if run.state else None,
    }

    # Include task states if this is a multi-task job
    if run.tasks:
        result["tasks"] = []
        for task in run.tasks:
            task_info = {
                "task_key": task.task_key,
                "state": task.state.life_cycle_state.value if task.state else "UNKNOWN",
                "result_state": task.state.result_state.value if task.state and task.state.result_state else None,
            }
            if task.run_id:
                task_info["run_id"] = task.run_id
            result["tasks"].append(task_info)

    return result


async def get_run_logs(client: WorkspaceClient, args: dict) -> dict:
    """Get logs from a run with optional offset for large logs."""
    run_id = args["run_id"]
    offset = args.get("offset", 0)
    max_size = args.get("max_size", MAX_LOG_SIZE)

    # Get run output which includes logs
    output = client.jobs.get_run_output(run_id=run_id)

    logs = output.logs if output.logs else ""
    total_size = len(logs)

    # Apply offset and size limit
    if offset > 0:
        logs = logs[offset:]

    logs_truncated_by_us = False
    if len(logs) > max_size:
        logs = logs[:max_size]
        logs_truncated_by_us = True
        logs += f"\n\n[... truncated, showing {max_size:,} chars starting at offset {offset}. Total size: {total_size:,} chars]"

    result = {
        "run_id": run_id,
        "logs": logs if logs else "No logs available",
        "logs_total_size": total_size,
        "logs_offset": offset,
        "logs_truncated_by_databricks": output.logs_truncated if hasattr(output, 'logs_truncated') else False,
        "logs_truncated_by_limit": logs_truncated_by_us,
    }

    # Include hint for fetching more if truncated
    if logs_truncated_by_us:
        result["next_offset"] = offset + max_size
        result["truncation_note"] = f"Use offset={offset + max_size} to continue reading logs"

    if output.error:
        result["error"] = output.error

    if output.error_trace:
        error_trace, trace_meta = truncate_text(output.error_trace, MAX_TEXT_SIZE, "error_trace")
        result["error_trace"] = error_trace
        result.update(trace_meta)

    return result


async def list_jobs(client: WorkspaceClient, args: dict) -> dict:
    """List jobs in the workspace."""
    name_filter = args.get("name_filter")
    limit = args.get("limit", 25)

    jobs_list = client.jobs.list(name=name_filter, limit=limit)

    jobs = []
    for job in jobs_list:
        jobs.append({
            "job_id": job.job_id,
            "name": job.settings.name if job.settings else "Unknown",
            "created_time": job.created_time
        })

    return {
        "jobs": jobs,
        "count": len(jobs)
    }


async def cancel_run(client: WorkspaceClient, args: dict) -> dict:
    """Cancel a run."""
    run_id = args["run_id"]

    client.jobs.cancel_run(run_id=run_id)

    return {
        "run_id": run_id,
        "status": "cancelled",
        "message": f"Run {run_id} has been cancelled"
    }


# ============================================================================
# Cluster Tool Implementations
# ============================================================================

async def list_clusters(client: WorkspaceClient, args: dict) -> dict:
    """List clusters in the workspace with truncation to avoid large payloads."""
    filter_by = args.get("filter_by", "all")
    limit = min(args.get("limit", 25), 100)  # Default 25, max 100
    clusters_iter = client.clusters.list()

    clusters = []
    total_matched = 0
    for cluster in clusters_iter:
        state = cluster.state.value if cluster.state else "UNKNOWN"

        # Apply filter (compare strings)
        if filter_by == "running" and state != "RUNNING":
            continue
        if filter_by == "terminated" and state != "TERMINATED":
            continue

        total_matched += 1
        if len(clusters) < limit:
            clusters.append({
                "cluster_id": cluster.cluster_id,
                "cluster_name": cluster.cluster_name,
                "state": state,
                "spark_version": cluster.spark_version,
                "node_type_id": cluster.node_type_id,
                "num_workers": cluster.num_workers,
                "creator": cluster.creator_user_name,
            })

    result = {
        "clusters": clusters,
        "returned": len(clusters),
        "total_matched": total_matched,
    }
    if total_matched > limit:
        result["truncated"] = True
        result["message"] = f"Showing {limit} of {total_matched} clusters. Use filter_by or increase limit (max 100) to see more."

    return result


async def get_cluster_status(client: WorkspaceClient, args: dict) -> dict:
    """Get detailed cluster status."""
    cluster_id = args["cluster_id"]
    cluster = client.clusters.get(cluster_id=cluster_id)

    return {
        "cluster_id": cluster.cluster_id,
        "cluster_name": cluster.cluster_name,
        "state": cluster.state.value if cluster.state else "UNKNOWN",
        "state_message": cluster.state_message,
        "spark_version": cluster.spark_version,
        "node_type_id": cluster.node_type_id,
        "driver_node_type_id": cluster.driver_node_type_id,
        "num_workers": cluster.num_workers,
        "autotermination_minutes": cluster.autotermination_minutes,
        "creator": cluster.creator_user_name,
        "start_time": cluster.start_time,
        "terminated_time": cluster.terminated_time,
    }


async def start_cluster(client: WorkspaceClient, args: dict) -> dict:
    """Start a terminated cluster, optionally waiting for it to be running."""
    from datetime import timedelta

    cluster_id = args["cluster_id"]
    wait = args.get("wait", True)
    timeout_minutes = args.get("timeout_minutes", 20)

    # Check current state first
    cluster = client.clusters.get(cluster_id=cluster_id)
    if cluster.state and cluster.state.value == "RUNNING":
        return {
            "cluster_id": cluster_id,
            "cluster_name": cluster.cluster_name,
            "status": "already_running",
            "state": "RUNNING",
            "message": "Cluster is already running"
        }

    if wait:
        # Start the cluster and wait for it to be running
        cluster = client.clusters.start_and_wait(
            cluster_id=cluster_id,
            timeout=timedelta(minutes=timeout_minutes)
        )
        return {
            "cluster_id": cluster.cluster_id,
            "cluster_name": cluster.cluster_name,
            "status": "started",
            "state": cluster.state.value if cluster.state else "UNKNOWN",
            "message": f"Cluster {cluster.cluster_name} is now running"
        }
    else:
        # Start without waiting
        client.clusters.start(cluster_id=cluster_id)
        return {
            "cluster_id": cluster_id,
            "cluster_name": cluster.cluster_name,
            "status": "starting",
            "state": "PENDING",
            "message": f"Cluster {cluster.cluster_name} is starting. Use databricks_get_cluster_status to check progress."
        }


async def stop_cluster(client: WorkspaceClient, args: dict) -> dict:
    """Stop/terminate a cluster."""
    cluster_id = args["cluster_id"]

    # Get cluster info before terminating
    cluster = client.clusters.get(cluster_id=cluster_id)
    cluster_name = cluster.cluster_name

    # Note: In Databricks SDK, delete() terminates the cluster (does not permanently delete)
    # permanent_delete() would permanently delete it
    client.clusters.delete(cluster_id=cluster_id)

    return {
        "cluster_id": cluster_id,
        "cluster_name": cluster_name,
        "status": "terminating",
        "message": f"Cluster {cluster_name} is being terminated"
    }


async def create_cluster(client: WorkspaceClient, args: dict) -> dict:
    """Create a new cluster with sensible defaults and Unity Catalog enabled."""
    from datetime import timedelta
    from databricks.sdk.service.compute import DataSecurityMode

    cluster_name = args["cluster_name"]
    num_workers = args.get("num_workers", 1)
    node_type_id = args.get("node_type_id", "m5.xlarge")
    spark_version = args.get("spark_version", "17.3.x-scala2.12")
    policy_id = args.get("policy_id")
    autotermination_minutes = args.get("autotermination_minutes", 120)
    wait = args.get("wait", False)
    timeout_minutes = args.get("timeout_minutes", 20)

    # Data security mode for Unity Catalog (default: SINGLE_USER)
    data_security_mode_str = args.get("data_security_mode", "SINGLE_USER")
    data_security_mode_map = {
        "SINGLE_USER": DataSecurityMode.SINGLE_USER,
        "USER_ISOLATION": DataSecurityMode.USER_ISOLATION,
        "NONE": DataSecurityMode.NONE,
    }
    data_security_mode = data_security_mode_map.get(data_security_mode_str, DataSecurityMode.SINGLE_USER)

    # For SINGLE_USER mode, get the user name (defaults to authenticated user)
    single_user_name = args.get("single_user_name")
    if data_security_mode == DataSecurityMode.SINGLE_USER and not single_user_name:
        # Get the current user's email
        current_user = client.current_user.me()
        single_user_name = current_user.user_name

    # Get user-provided custom tags (optional)
    custom_tags = args.get("custom_tags", {})

    # Build create kwargs
    create_kwargs = {
        "cluster_name": cluster_name,
        "spark_version": spark_version,
        "node_type_id": node_type_id,
        "num_workers": num_workers,
        "autotermination_minutes": autotermination_minutes,
        "data_security_mode": data_security_mode,
    }

    # Add optional parameters if provided
    if custom_tags:
        create_kwargs["custom_tags"] = custom_tags

    # Add single_user_name for SINGLE_USER mode
    if data_security_mode == DataSecurityMode.SINGLE_USER:
        create_kwargs["single_user_name"] = single_user_name

    if policy_id:
        create_kwargs["policy_id"] = policy_id

    if wait:
        cluster = client.clusters.create_and_wait(
            **create_kwargs,
            timeout=timedelta(minutes=timeout_minutes)
        )
        return {
            "cluster_id": cluster.cluster_id,
            "cluster_name": cluster.cluster_name,
            "state": cluster.state.value if cluster.state else "UNKNOWN",
            "status": "created_and_running",
            "message": f"Cluster '{cluster_name}' created and is now running"
        }
    else:
        # create() returns a Wait object, get the response
        wait_obj = client.clusters.create(**create_kwargs)
        # The Wait object has a cluster_id attribute
        cluster_id = wait_obj.cluster_id
        return {
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "status": "creating",
            "message": f"Cluster '{cluster_name}' creation started. Use databricks_get_cluster_status to check progress."
        }


async def list_cluster_policies(client: WorkspaceClient, args: dict) -> dict:
    """List available cluster policies."""
    policies = client.cluster_policies.list()

    result = []
    for policy in policies:
        result.append({
            "policy_id": policy.policy_id,
            "name": policy.name,
            "description": policy.description,
        })

    return {"policies": result, "count": len(result)}


# ============================================================================
# Interactive Execution Tool Implementations
# ============================================================================

async def create_context(client: WorkspaceClient, args: dict) -> dict:
    """Create an execution context on a cluster."""
    from databricks.sdk.service.compute import Language, ContextStatus
    from datetime import timedelta

    cluster_id = args["cluster_id"]
    language_str = args.get("language", "python")

    # Map string to Language enum
    language_map = {
        "python": Language.PYTHON,
        "scala": Language.SCALA,
        "sql": Language.SQL,
        "r": Language.R,
    }
    language = language_map.get(language_str.lower(), Language.PYTHON)

    # Create context and wait for it to be ready
    context = client.command_execution.create_and_wait(
        cluster_id=cluster_id,
        language=language,
        timeout=timedelta(minutes=5)
    )

    # Verify context was created successfully
    if context.status != ContextStatus.RUNNING:
        return {
            "success": False,
            "cluster_id": cluster_id,
            "status": context.status.value if context.status else "UNKNOWN",
            "error": f"Context creation failed with status: {context.status}"
        }

    return {
        "success": True,
        "context_id": context.id,
        "cluster_id": cluster_id,
        "language": language_str,
        "status": context.status.value if context.status else "UNKNOWN",
        "message": f"Execution context created. Use databricks_execute_cell with context_id={context.id}"
    }


async def execute_cell(client: WorkspaceClient, args: dict) -> dict:
    """Execute code in an execution context with output size protection."""
    from databricks.sdk.service.compute import Language, CommandStatus, ResultType
    from datetime import timedelta
    import json

    cluster_id = args["cluster_id"]
    context_id = args["context_id"]
    code = args["code"]
    language_str = args.get("language", "python")
    timeout_minutes = args.get("timeout_minutes", 30)

    # Map string to Language enum
    language_map = {
        "python": Language.PYTHON,
        "scala": Language.SCALA,
        "sql": Language.SQL,
        "r": Language.R,
    }
    language = language_map.get(language_str.lower(), Language.PYTHON)

    # Execute command and wait for result
    response = client.command_execution.execute_and_wait(
        cluster_id=cluster_id,
        context_id=context_id,
        command=code,
        language=language,
        timeout=timedelta(minutes=timeout_minutes)
    )

    # Determine success/failure
    is_error = (
        response.status == CommandStatus.ERROR or
        (response.results and response.results.result_type == ResultType.ERROR)
    )

    result = {
        "success": not is_error,
        "status": response.status.value if response.status else "UNKNOWN",
        "command_id": response.id,
    }

    # Extract results with truncation protection
    if response.results:
        results = response.results
        result["result_type"] = results.result_type.value if results.result_type else None
        result["truncated_by_databricks"] = results.truncated

        # Handle data - could be string, dict, list, etc.
        data = results.data
        if data is not None:
            # Convert to string for size checking if needed
            if isinstance(data, str):
                data_str = data
            else:
                try:
                    data_str = json.dumps(data)
                except (TypeError, ValueError):
                    data_str = str(data)

            if len(data_str) > MAX_TEXT_SIZE:
                # For table data (list of rows), try to truncate by rows
                if isinstance(data, list) and len(data) > 0:
                    # Estimate rows to keep
                    avg_row_size = len(data_str) / len(data)
                    rows_to_keep = max(1, int(MAX_TEXT_SIZE / avg_row_size))
                    result["data"] = data[:rows_to_keep]
                    result["data_truncated"] = True
                    result["data_total_rows"] = len(data)
                    result["data_shown_rows"] = rows_to_keep
                    result["truncation_note"] = f"Showing {rows_to_keep} of {len(data)} rows. Add LIMIT to your query for smaller results."
                else:
                    # For string data, truncate by characters
                    truncated_data, meta = truncate_text(data_str, MAX_TEXT_SIZE, "data")
                    result["data"] = truncated_data
                    result.update(meta)
            else:
                result["data"] = data

        # Include error info if present
        if results.cause:
            result["error_cause"] = results.cause
        if results.summary:
            result["error_summary"] = results.summary

        # Include schema for table results (useful for understanding structure)
        if results.schema:
            result["schema"] = results.schema

    return result


async def destroy_context(client: WorkspaceClient, args: dict) -> dict:
    """Destroy an execution context."""
    cluster_id = args["cluster_id"]
    context_id = args["context_id"]

    client.command_execution.destroy(
        cluster_id=cluster_id,
        context_id=context_id
    )

    return {
        "context_id": context_id,
        "cluster_id": cluster_id,
        "status": "destroyed",
        "message": "Execution context has been destroyed"
    }


# ============================================================================
# Main Entry Point
# ============================================================================

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
