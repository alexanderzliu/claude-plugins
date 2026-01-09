---
name: Databricks Notebook Development
description: This skill should be used when the user asks to "develop on Databricks", "create a Databricks notebook", "build a notebook in Databricks", "write code for Databricks", "run code on Databricks", "develop something for Databricks", "iterate on a Databricks notebook", or mentions interactive notebook development with clusters. Provides workflow guidance for developing and testing notebooks using Databricks MCP tools.
---

# Databricks Notebook Development Workflow

This skill guides the development of Databricks notebooks using MCP tools for cluster management, interactive execution, and notebook operations. Follow this workflow for iterative notebook development with immediate feedback.

## Workflow Overview

The development workflow consists of four phases:

1. **Setup**: Gather user requirements and prepare cluster
2. **Development**: Write notebook cells and save to workspace
3. **Testing**: Execute cells interactively and debug failures
4. **Completion**: Summarize results and clean up

## Phase 1: Setup

### Gather User Information

Before starting development, collect essential information from the user:

1. **Workspace path**: Ask for the user's workspace email address
   - If provided: Use `/Workspace/Users/{email}/` as the base path
   - If not provided: Default to `/Workspace/Shared/` for shared workspace

2. **Notebook name**: What should the notebook be called?

3. **Development goal**: What should the notebook accomplish?

### Cluster Setup

Determine whether to use an existing cluster or create a new one.

**Option A: Use existing cluster (preferred if user has one)**

1. Ask user for cluster name or check if they have a preferred cluster
2. Find cluster ID:
   ```
   databricks_list_clusters()
   ```
3. Get cluster status:
   ```
   databricks_get_cluster_status(cluster_id="...")
   ```
4. Start cluster if terminated:
   ```
   databricks_start_cluster(cluster_id="...", wait=true)
   ```

**Option B: Create new cluster**

Create a development cluster with recommended defaults:
```
databricks_create_cluster(
  cluster_name="dev-{username}-{date}",
  num_workers=1,
  node_type_id="m5.xlarge",
  autotermination_minutes=120,
  wait=true
)
```

These defaults provide:
- Single worker node for cost efficiency
- m5.xlarge instances for good memory/compute balance
- 2-hour auto-termination to prevent forgotten clusters
- Waiting ensures cluster is ready before proceeding

### Create Execution Context

Once the cluster is running, create an execution context:
```
databricks_create_context(cluster_id="...", language="python")
```

Save the returned `context_id` - this is needed for all subsequent cell executions.

**Important**: The context maintains state between executions. Variables defined in one cell persist to later cells.

## Phase 2: Development

### Notebook Format

Databricks notebooks use `# COMMAND ----------` separators between cells:

```python
# Databricks notebook source
# Cell 0: Imports and setup
import pandas as pd
from pyspark.sql import functions as F

# COMMAND ----------

# Cell 1: Load data
df = spark.read.table("my_database.my_table")

# COMMAND ----------

# Cell 2: Transform data
result = df.filter(F.col("status") == "active")

# COMMAND ----------

# Cell 3: Display results
display(result)
```

### Writing Notebooks

**For new notebooks**: Use `databricks_write_notebook`:
```
databricks_write_notebook(
  notebook_path="/Workspace/Users/user@example.com/my_notebook",
  content="# Databricks notebook source\n..."
)
```

**For existing notebooks**: First read the current content:
```
databricks_read_notebook(notebook_path="...")
```

Then decide based on change scope:
- **Small changes (1-3 cells)**: Use `databricks_update_notebook_cell`
- **Large changes**: Use `databricks_write_notebook` to replace entire content

### Cell Updates

Update specific cells without rewriting the entire notebook:

**Single cell:**
```
databricks_update_notebook_cell(
  notebook_path="...",
  cell_index=2,
  new_content="# Fixed code\nresult = df.filter(F.col('status').isNotNull())"
)
```

**Multiple cells:**
```
databricks_update_notebook_cell(
  notebook_path="...",
  updates=[
    {"index": 2, "content": "# Fixed cell 2"},
    {"index": 4, "content": "# Fixed cell 4"}
  ]
)
```

**Important**: Cell indices are 0-based. Always read the notebook first to confirm cell indices before updating.

## Phase 3: Testing

### Cell-by-Cell Execution

Execute each cell using `databricks_execute_cell` and verify success before proceeding:

```
databricks_execute_cell(
  cluster_id="...",
  context_id="...",
  code="import pandas as pd\nprint('Setup complete')"
)
```

**Execution flow:**
1. Execute cell 0 (imports/setup)
2. Check `success` field in response
3. If successful, proceed to next cell
4. If failed, debug and fix before continuing

### Handling Failures

When a cell fails, the response includes:
- `success: false`
- `error_cause`: The exception message
- `error_summary`: Brief error description

**Debugging workflow:**
1. Analyze the error message
2. Identify the fix
3. Update the cell with `databricks_update_notebook_cell`
4. Re-execute the cell
5. Continue once successful

### State Persistence

Variables persist within the execution context:

```python
# Cell 1
x = 10
```
```python
# Cell 2 - x is still available
print(x * 2)  # Output: 20
```

This allows iterative development where each cell builds on previous work.

## Phase 4: Completion

### Summary

After all cells execute successfully, provide a summary including:

1. **What was built**: Brief description of the notebook's functionality
2. **Key results**: Important outputs or metrics from the execution
3. **Notebook location**: Full workspace path to the saved notebook
4. **Cluster info**: Cluster name/ID used for development

### Cleanup (Optional)

Offer to clean up resources:

1. **Destroy context** (recommended):
   ```
   databricks_destroy_context(cluster_id="...", context_id="...")
   ```

2. **Stop cluster** (if user is done for the day):
   ```
   databricks_stop_cluster(cluster_id="...")
   ```

## Best Practices

### Execution Timing

After starting a notebook run with `databricks_run_notebook`, wait approximately 30 seconds before checking status. Use `databricks_wait_for_run` rather than repeatedly calling `databricks_get_run_output`.

### Error Handling in Notebooks

Include try/except blocks for operations that might fail:
```python
try:
    df = spark.read.table("database.table")
except Exception as e:
    print(f"Failed to read table: {e}")
    raise
```

### Memory Management

For large datasets, include cleanup in notebook cells:
```python
# Clear cached dataframes when no longer needed
df.unpersist()
```

### Notebook Organization

Structure notebooks with clear sections:
1. **Setup**: Imports, configurations, parameters
2. **Data Loading**: Read from sources
3. **Transformations**: Business logic
4. **Output**: Write results, display summaries

## Quick Reference

### Common Workspace Paths

| Path Pattern | Description |
|--------------|-------------|
| `/Workspace/Users/{email}/` | User's personal folder |
| `/Workspace/Shared/` | Shared workspace |
| `/Workspace/Repos/{email}/{repo}/` | Git repository |

### Tool Selection Guide

| Task | Tool |
|------|------|
| Find cluster by name | `databricks_list_clusters` |
| Check if cluster is running | `databricks_get_cluster_status` |
| Start stopped cluster | `databricks_start_cluster` |
| Create new cluster | `databricks_create_cluster` |
| Prepare for execution | `databricks_create_context` |
| Run single cell | `databricks_execute_cell` |
| Read existing notebook | `databricks_read_notebook` |
| Create new notebook | `databricks_write_notebook` |
| Fix specific cells | `databricks_update_notebook_cell` |
| Run entire notebook | `databricks_run_notebook` |
| Wait for run completion | `databricks_wait_for_run` |

## Additional Resources

### Reference Files

For complete tool documentation including all parameters and return values:
- **`references/tools.md`** - Complete MCP tools reference with parameters, return values, and examples
