# Databricks MCP Tools Reference

Complete reference for all Databricks MCP tools used in notebook development workflows.

## Cluster Tools

### databricks_list_clusters

List all clusters in the workspace with their current status.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filter_by` | string | No | Filter by state: `"all"` (default), `"running"`, `"terminated"` |

**Returns:** Array of clusters with `cluster_id`, `cluster_name`, `state`, `spark_version`, `node_type_id`, `num_workers`, `creator`

**Example:**
```json
{"filter_by": "running"}
```

---

### databricks_get_cluster_status

Get detailed status and information about a specific cluster.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID to check |

**Returns:** Detailed cluster info including `state`, `state_message`, `spark_version`, `node_type_id`, `num_workers`, `autotermination_minutes`, `start_time`, `terminated_time`

---

### databricks_start_cluster

Start a terminated cluster and optionally wait until running.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID to start |
| `wait` | boolean | No | Wait for cluster to be running (default: `true`) |
| `timeout_minutes` | integer | No | Maximum wait time in minutes (default: `20`) |

**Returns:** Status with `cluster_id`, `cluster_name`, `state`, `status` ("started", "already_running", or "starting")

**Note:** If cluster is already running, returns immediately with `status: "already_running"`.

---

### databricks_stop_cluster

Stop/terminate a running cluster.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID to stop |

**Returns:** Confirmation with `status: "terminating"`

---

### databricks_create_cluster

Create a new cluster with configurable settings.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_name` | string | Yes | Name for the cluster |
| `num_workers` | integer | No | Number of worker nodes (default: `1`, use `0` for single-node) |
| `node_type_id` | string | No | Node type (default: `"m5.xlarge"`) |
| `spark_version` | string | No | Spark runtime version (default: `"17.3.x-scala2.12"`) |
| `policy_id` | string | No | Cluster policy ID (optional, use if your organization requires a specific policy) |
| `autotermination_minutes` | integer | No | Auto-terminate after idle minutes (default: `120`) |
| `custom_tags` | object | No | Custom tags for the cluster (optional key-value pairs) |
| `wait` | boolean | No | Wait for cluster to be running (default: `false`) |
| `timeout_minutes` | integer | No | Max wait time if wait=true (default: `20`) |

**Returns:** `cluster_id`, `cluster_name`, `status` ("creating" or "created_and_running")

**Recommended defaults for development:**
- `num_workers: 1` - Single worker for development
- `node_type_id: "m5.xlarge"` - Good balance of memory/compute
- `autotermination_minutes: 120` - Auto-stop after 2 hours idle
- `wait: true` - Wait for cluster to be ready before proceeding

---

### databricks_list_cluster_policies

List available cluster policies to find policy_id for cluster creation.

**Parameters:** None

**Returns:** Array of policies with `policy_id`, `name`, `description`

---

## Interactive Execution Tools

### databricks_create_context

Create an execution context on a running cluster for interactive code execution.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The running cluster ID |
| `language` | string | No | Programming language: `"python"` (default), `"scala"`, `"sql"`, `"r"` |

**Returns:** `context_id` for use with `databricks_execute_cell`, plus `cluster_id`, `language`, `status`

**Important:** The cluster must be in RUNNING state before creating a context.

---

### databricks_execute_cell

Execute code in an execution context and get the output. Variables and state persist between calls.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID |
| `context_id` | string | Yes | The execution context ID from `databricks_create_context` |
| `code` | string | Yes | The code to execute |
| `language` | string | No | Programming language (default: `"python"`) |
| `timeout_minutes` | integer | No | Maximum execution time in minutes (default: `30`) |

**Returns:**
- `success`: boolean indicating if execution succeeded
- `status`: execution status
- `data`: output data (if any)
- `result_type`: type of result
- `error_cause`, `error_summary`: error details (if failed)
- `schema`: schema for table results

**Key behavior:**
- Variables persist between calls within the same context
- Large outputs are automatically truncated
- Errors include traceback information

---

### databricks_destroy_context

Destroy an execution context when done with interactive execution.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID |
| `context_id` | string | Yes | The execution context ID to destroy |

**Returns:** Confirmation with `status: "destroyed"`

---

## Notebook Tools

### databricks_list_notebooks

List notebooks in a workspace directory.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Workspace directory path to list |
| `limit` | integer | No | Maximum items to return (default: `100`) |
| `offset` | integer | No | Skip this many items for pagination (default: `0`) |

**Returns:** Array of items with `path`, `type`, `language`, plus pagination info (`has_more`, `next_offset`)

**Example paths:**
- `/Workspace/Users/user@example.com/` - User's personal folder
- `/Workspace/Shared/` - Shared workspace

---

### databricks_read_notebook

Read the contents of a Databricks notebook (.py file with `# COMMAND` separators).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to the notebook |
| `cell_offset` | integer | No | Start reading from this cell index, 0-based (default: `0`) |
| `cell_limit` | integer | No | Maximum number of cells to return (default: all cells) |

**Returns:**
- `path`: notebook path
- `total_cells`: total number of cells in notebook
- `cells`: array of cell contents (strings)
- `cells_returned`: number of cells in this response
- `cell_offset`: starting cell index
- `has_more`, `next_offset`: pagination info if more cells exist

**Note:** Cells are indexed 0-based. Large cells are automatically truncated.

---

### databricks_write_notebook

Write/update a Databricks notebook.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to the notebook |
| `content` | string | Yes | Notebook content (Python with `# COMMAND ----------` separators) |
| `overwrite` | boolean | No | Whether to overwrite existing notebook (default: `true`) |

**Returns:** Confirmation with `status: "success"`

**Notebook format:**
```python
# Databricks notebook source
# First cell content here

# COMMAND ----------

# Second cell content here

# COMMAND ----------

# Third cell content here
```

---

### databricks_update_notebook_cell

Update specific cell(s) in a notebook without rewriting the entire content.

**Parameters (single cell):**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to the notebook |
| `cell_index` | integer | Yes* | 0-based index of the cell to update |
| `new_content` | string | Yes* | New content for the cell |

**Parameters (batch update):**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to the notebook |
| `updates` | array | Yes* | Array of `{index, content}` objects |

*Use either `cell_index`+`new_content` OR `updates`, not both.

**Returns:** `updated_cells` array showing which cells were modified, `total_cells`

**When to use:**
- Single cell fix: Use `cell_index` + `new_content`
- Multiple fixes: Use `updates` array for efficiency
- Full rewrite: Use `databricks_write_notebook` instead

---

## Notebook Run Tools

### databricks_run_notebook

Run a Databricks notebook using serverless compute.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to the notebook |
| `parameters` | object | No | Notebook widget parameters as key-value pairs |
| `timeout_minutes` | integer | No | Timeout in minutes (default: `30`) |

**Returns:** `run_id` for tracking the run

**Note:** This runs the entire notebook on serverless compute. For cell-by-cell execution, use `databricks_execute_cell` instead.

---

### databricks_get_run_output

Get the output of a notebook run, including cell-by-cell results.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID returned by `databricks_run_notebook` |

**Returns:**
- `state`: lifecycle state (PENDING, RUNNING, TERMINATED, etc.)
- `result_state`: result state (SUCCESS, FAILED, etc.)
- `notebook_output`: notebook result if available
- `error`, `error_trace`: error details if failed
- `logs`: execution logs

---

### databricks_wait_for_run

Wait for a notebook run to complete, polling until done.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID to wait for |
| `timeout_minutes` | integer | No | Maximum time to wait in minutes (default: `30`) |
| `poll_interval_seconds` | integer | No | Seconds between status checks (default: `10`) |

**Returns:** Same as `databricks_get_run_output` once run completes

**Important:** Prefer this over repeatedly calling `databricks_get_run_output` to check status.

---

### databricks_cancel_run

Cancel a running notebook or job run.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID to cancel |

**Returns:** Confirmation with `status: "cancelled"`

---

## Size Limits and Truncation

The MCP server enforces these limits to prevent overwhelming context:

| Limit | Value | Description |
|-------|-------|-------------|
| `MAX_TEXT_SIZE` | 100,000 chars | Per text field |
| `MAX_CELL_CONTENT` | 50,000 chars | Per notebook cell |
| `MAX_LIST_ITEMS` | 100 | For list operations |
| `MAX_LOG_SIZE` | 80,000 chars | For logs |

When content exceeds limits, responses include truncation metadata (`*_truncated: true`, `*_total_size`, `*_shown_size`).
