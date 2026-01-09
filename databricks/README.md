# Databricks Plugin

Databricks integration for Claude Code. Run notebooks, monitor cell outputs, create jobs, and validate orchestration - enabling iterative development directly from Claude Code.

## Table of Contents

- [Features](#features)
- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Environment Configuration](#1-configure-environment-variables)
  - [Installation](#2-install-the-plugin)
- [Available Tools](#available-tools)
  - [Notebook Tools](#notebook-tools)
  - [Job Tools](#job-tools)
  - [Cluster Tools](#cluster-tools)
  - [Interactive Execution Tools](#interactive-execution-tools)
- [Example Workflows](#example-workflows)
- [Configuration Options](#configuration-options)
- [Troubleshooting](#troubleshooting)
- [Skills](#skills)
- [Future Enhancements](#future-enhancements)

## Features

### Notebook Development
- **Run notebooks** using serverless compute with parameters
- **Monitor cell outputs** to validate results
- **Read/write notebooks** (`.py` files with `# COMMAND` separators)
- **Wait for completion** with configurable polling

### Cluster Management
- **List and manage clusters** - find, start, stop, create clusters
- **Interactive execution** - run code cell-by-cell with state persistence

### Job Orchestration
- **Create jobs** with notebook tasks and dependencies
- **Run jobs** and monitor task status
- **Get logs** (stdout/stderr) for debugging
- **Cancel runs** when needed

### Skills

This plugin includes workflow guidance skills:

| Skill | Description |
|-------|-------------|
| **notebook-development** | Guided workflow for developing notebooks on Databricks with cluster setup, interactive execution, and debugging |

The skill triggers when you ask to "develop on Databricks", "create a Databricks notebook", "write code for Databricks", etc.

## Setup

### Prerequisites

Before installing, ensure you have:

1. **Databricks Workspace Access**
   - A Databricks workspace URL (e.g., `https://your-workspace.cloud.databricks.com`)
   - Permission to create Personal Access Tokens
   - For serverless: Serverless compute enabled in your workspace
   - For interactive execution: Access to create/manage clusters

2. **uv Package Manager** (installed automatically, or manually):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # or
   pip install uv
   ```

### 1. Configure Environment Variables

Set these environment variables in your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-personal-access-token"
```

After adding these lines, reload your shell or source the file:
```bash
source ~/.bashrc  # or ~/.zshrc
```

**Verify the variables are set:**
```bash
echo $DATABRICKS_HOST  # Should print your workspace URL
```

**Getting a Personal Access Token (PAT):**

1. Log into your Databricks workspace
2. Click your username (top-right corner) → **User Settings**
3. Navigate to **Developer** → **Access tokens**
4. Click **Generate new token**
5. Set a description (e.g., "Claude Code") and expiration
6. Copy the token immediately (it won't be shown again)

> **Note:** Store your token securely. Consider using a secrets manager or environment variable file that's not committed to version control.

### 2. Install the Plugin

```bash
claude plugin install databricks@claude-plugins
```

Python dependencies (`databricks-sdk`, `mcp`) are installed automatically via `uv` when the plugin starts.

**Verify Installation:**
```bash
# Test that the plugin loads
claude mcp list
# Should show "databricks" in the list
```

## Available Tools

### Notebook Tools

| Tool | Description |
|------|-------------|
| `databricks_run_notebook` | Run a notebook using serverless compute, returns `run_id` |
| `databricks_get_run_output` | Get cell outputs and results from a run |
| `databricks_wait_for_run` | Poll until a run completes, then return output |
| `databricks_read_notebook` | Read notebook content, parsed into cells |
| `databricks_write_notebook` | Write/update entire notebook content |
| `databricks_update_notebook_cell` | Update specific cell(s) without rewriting entire notebook |
| `databricks_list_notebooks` | List notebooks in a workspace directory |

<details>
<summary><strong>Notebook Tool Parameters</strong></summary>

#### `databricks_run_notebook`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Full workspace path (e.g., `/Workspace/Users/you@email.com/notebook`) |
| `parameters` | object | No | Widget parameters as key-value pairs |
| `timeout_minutes` | integer | No | Timeout in minutes (default: 30) |

#### `databricks_get_run_output`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID from `databricks_run_notebook` |

#### `databricks_wait_for_run`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID to wait for |
| `timeout_minutes` | integer | No | Max wait time in minutes (default: 30) |
| `poll_interval_seconds` | integer | No | Seconds between status checks (default: 10) |

#### `databricks_read_notebook`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to the notebook |
| `cell_offset` | integer | No | Start from this cell index (default: 0) |
| `cell_limit` | integer | No | Max cells to return (default: all) |

#### `databricks_write_notebook`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to write to |
| `content` | string | Yes | Python content with `# COMMAND ----------` cell separators |
| `overwrite` | boolean | No | Overwrite if exists (default: true) |

#### `databricks_update_notebook_cell`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notebook_path` | string | Yes | Workspace path to the notebook |
| `cell_index` | integer | No* | 0-based index of cell to update |
| `new_content` | string | No* | New content for the cell |
| `updates` | array | No* | Batch updates: `[{index, content}, ...]` |

*Use either `cell_index`+`new_content` OR `updates`, not both.

#### `databricks_list_notebooks`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Workspace directory path to list |
| `limit` | integer | No | Max items to return (default: 100) |
| `offset` | integer | No | Skip this many items for pagination (default: 0) |

</details>

### Job Tools

| Tool | Description |
|------|-------------|
| `databricks_create_job` | Create a job with notebook tasks |
| `databricks_run_job` | Trigger a job run |
| `databricks_get_job_run_status` | Get run status with task details |
| `databricks_get_run_logs` | Get stdout/stderr logs |
| `databricks_list_jobs` | List jobs in workspace |
| `databricks_cancel_run` | Cancel a running job |

<details>
<summary><strong>Job Tool Parameters</strong></summary>

#### `databricks_create_job`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Job name |
| `tasks` | array | Yes | Array of task definitions |

Task definition:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_key` | string | Yes | Unique task identifier |
| `notebook_path` | string | Yes | Workspace path to notebook |
| `depends_on` | array | No | List of task_keys this depends on |
| `parameters` | object | No | Notebook parameters |

#### `databricks_run_job`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | integer | Yes | The job ID to run |
| `parameters` | object | No | Notebook parameters to override |

#### `databricks_get_job_run_status`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID to check |

#### `databricks_get_run_logs`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID |
| `offset` | integer | No | Character offset (default: 0) |
| `max_size` | integer | No | Max chars to return (default: 80000) |

#### `databricks_list_jobs`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name_filter` | string | No | Filter jobs by name (substring match) |
| `limit` | integer | No | Max jobs to return (default: 25) |

#### `databricks_cancel_run`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `run_id` | integer | Yes | The run ID to cancel |

</details>

### Cluster Tools

| Tool | Description |
|------|-------------|
| `databricks_list_clusters` | List all clusters with their status |
| `databricks_get_cluster_status` | Get detailed status of a cluster |
| `databricks_start_cluster` | Start a terminated cluster |
| `databricks_stop_cluster` | Stop/terminate a running cluster |
| `databricks_create_cluster` | Create a new cluster with custom configuration |
| `databricks_list_cluster_policies` | List available cluster policies |

<details>
<summary><strong>Cluster Tool Parameters</strong></summary>

#### `databricks_list_clusters`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filter_by` | string | No | `"all"`, `"running"`, or `"terminated"` (default: all) |
| `limit` | integer | No | Max clusters to return (default: 25, max: 100) |

#### `databricks_get_cluster_status`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID to check |

#### `databricks_stop_cluster`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID to stop/terminate |

#### `databricks_create_cluster`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_name` | string | Yes | Name for the cluster |
| `num_workers` | integer | No | Worker nodes (default: 1, use 0 for single-node) |
| `node_type_id` | string | No | Node type (default: m5.xlarge) |
| `spark_version` | string | No | Spark runtime (default: 17.3.x-scala2.12) |
| `policy_id` | string | No | Cluster policy ID |
| `data_security_mode` | string | No | `"SINGLE_USER"`, `"USER_ISOLATION"`, `"NONE"` (default: SINGLE_USER) |
| `single_user_name` | string | No | User email for SINGLE_USER mode |
| `autotermination_minutes` | integer | No | Auto-terminate idle time (default: 120) |
| `custom_tags` | object | No | Custom tags for the cluster (optional key-value pairs) |
| `wait` | boolean | No | Wait for running state (default: false) |
| `timeout_minutes` | integer | No | Wait timeout if wait=true (default: 20) |

#### `databricks_start_cluster`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID to start |
| `wait` | boolean | No | Wait until running (default: true) |
| `timeout_minutes` | integer | No | Wait timeout (default: 20) |

</details>

### Interactive Execution Tools

| Tool | Description |
|------|-------------|
| `databricks_create_context` | Create execution context on a running cluster |
| `databricks_execute_cell` | Execute code and get immediate output |
| `databricks_destroy_context` | Clean up an execution context |

<details>
<summary><strong>Interactive Execution Parameters</strong></summary>

#### `databricks_create_context`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | Running cluster ID |
| `language` | string | No | `"python"`, `"scala"`, `"sql"`, `"r"` (default: python) |

#### `databricks_execute_cell`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID |
| `context_id` | string | Yes | Context ID from create_context |
| `code` | string | Yes | Code to execute |
| `language` | string | No | `"python"`, `"scala"`, `"sql"`, `"r"` (default: python) |
| `timeout_minutes` | integer | No | Execution timeout (default: 30) |

#### `databricks_destroy_context`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cluster_id` | string | Yes | The cluster ID |
| `context_id` | string | Yes | Context ID to destroy |

</details>

## Example Workflows

### Iterative Notebook Development

```
1. Claude reads existing notebook:
   databricks_read_notebook(path="/Workspace/Users/you/my_notebook")
   → Returns cells array with indices 0, 1, 2, ...

2. Claude modifies and writes changes:
   databricks_write_notebook(path="...", content="...")

3. Claude runs the notebook:
   databricks_run_notebook(path="...", parameters={"date": "2024-01-01"})
   → Returns run_id=12345

4. Claude waits for completion and checks output:
   databricks_wait_for_run(run_id=12345)
   → Returns cell outputs, errors, logs

5. If cell 4 has an error, Claude fixes just that cell:
   databricks_update_notebook_cell(
     notebook_path="...",
     cell_index=4,
     new_content="# Fixed code\ndf = df.dropna()"
   )
   → More efficient than rewriting entire notebook

6. Claude re-runs to verify the fix
```

### Job Orchestration

```
1. Claude creates a job with tasks:
   databricks_create_job(
     name="ETL Pipeline",
     tasks=[
       {task_key: "extract", notebook_path: "/Workspace/.../extract"},
       {task_key: "transform", notebook_path: "...", depends_on: ["extract"]},
       {task_key: "load", notebook_path: "...", depends_on: ["transform"]}
     ]
   )
   → Returns job_id=789

2. Claude runs the job:
   databricks_run_job(job_id=789)
   → Returns run_id=12346

3. Claude monitors status:
   databricks_get_job_run_status(run_id=12346)
   → Shows each task's state

4. If a task fails, Claude gets logs:
   databricks_get_run_logs(run_id=12346)
```

### Interactive Cell Execution

For cell-by-cell execution with immediate output (requires a classic all-purpose cluster):

```
1. List available clusters:
   databricks_list_clusters(filter_by="all")

2. Start a cluster (if terminated):
   databricks_start_cluster(cluster_id="0123-456789-abcdef")
   → Waits until cluster is RUNNING

3. Create an execution context:
   databricks_create_context(cluster_id="...", language="python")
   → Returns context_id="abc123"

4. Execute cells interactively:
   databricks_execute_cell(cluster_id="...", context_id="abc123", code="x = 10")
   → Returns: {"success": true, "data": null, "status": "Finished"}

   databricks_execute_cell(..., code="print(x * 2)")
   → Returns: {"success": true, "data": "20", "status": "Finished"}  # x persists!

5. Clean up when done:
   databricks_destroy_context(cluster_id="...", context_id="abc123")

6. Optionally stop the cluster:
   databricks_stop_cluster(cluster_id="...")
```

## Configuration Options

### Execution Modes

This plugin supports two execution modes:

| Mode | Tools | Compute | Cell Output |
|------|-------|---------|-------------|
| **Batch** | `databricks_run_notebook` | Serverless | Final result only |
| **Interactive** | `databricks_execute_cell` | Classic cluster | Per-cell output |

Use **batch mode** for running complete notebooks with serverless compute. Use **interactive mode** when you need to see output from individual cells or iterate on code.

### Serverless Compute (Batch Mode)

Batch mode uses Databricks serverless compute for running notebooks and jobs. Serverless compute automatically provisions and manages compute resources, eliminating the need to configure clusters.

**Requirements:**
- Your Databricks workspace must have serverless compute enabled
- Your account must have appropriate permissions for serverless workloads

### Classic Clusters (Interactive Mode)

Interactive mode requires a classic all-purpose cluster. The Command Execution API does not support serverless compute.

**Requirements:**
- An existing all-purpose cluster in your workspace
- Permissions to start/stop clusters and execute commands

### Notebook Parameters

Pass widget parameters when running notebooks:

```json
{
  "notebook_path": "/Workspace/.../my_notebook",
  "parameters": {
    "date": "2024-01-01",
    "environment": "dev"
  }
}
```

## Troubleshooting

### "DATABRICKS_HOST and DATABRICKS_TOKEN must be set"
Ensure environment variables are exported before starting Claude Code.

### "Notebook not found"
- Check the full workspace path (should start with `/Workspace/`)
- Verify you have access to the notebook

### "Serverless compute is not enabled"
- Serverless compute must be enabled in your Databricks workspace
- Contact your workspace administrator to enable serverless compute

### Run takes too long
- Increase `timeout_minutes` in run or wait commands
- Serverless compute has automatic scaling, but initial cold starts may take longer

## Skills

### notebook-development

The **notebook-development** skill provides guided workflow assistance for developing Databricks notebooks. It triggers automatically when you ask Claude to develop something on Databricks.

**Trigger phrases:**
- "develop on Databricks"
- "create a Databricks notebook"
- "build a notebook in Databricks"
- "write code for Databricks"
- "iterate on a Databricks notebook"

**What it provides:**
1. **Setup guidance** - Asks for workspace path, helps with cluster setup (existing or new)
2. **Development workflow** - Guides notebook creation and cell updates
3. **Testing workflow** - Cell-by-cell execution with debugging
4. **Best practices** - Notebook organization, error handling, memory management

**Example interaction:**
```
User: Help me develop a data processing notebook on Databricks

Claude: [Skill activates]
- Asks for your workspace email
- Asks about cluster preference (existing or new)
- Guides through notebook development
- Executes cells interactively
- Helps debug any failures
```

## Future Enhancements

### Job Deployment Skill
A companion skill for deploying notebooks as scheduled jobs with monitoring and alerting configuration.

### Custom Cluster Support for Batch Jobs
Currently, batch mode (`databricks_run_notebook`) uses serverless compute exclusively. For workspaces without serverless enabled, we could add support for:
- Running batch notebooks on job clusters with custom configurations
- Specifying spark version, node type, and worker count for batch jobs

### Workspace Path Helper
Add a tool to resolve shorthand paths to full workspace paths:
- `~/my_notebook` → `/Workspace/Users/user@example.com/my_notebook`
- `shared/my_notebook` → `/Workspace/Shared/my_notebook`

This would reduce friction when specifying notebook paths.
