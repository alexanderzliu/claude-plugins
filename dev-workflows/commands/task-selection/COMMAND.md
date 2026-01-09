---
name: Task Selection
description: Select and set up tasks from a Notion task board for development, with automatic git worktree creation for parallel work.
---

# Task Selection

Select and set up tasks from a Notion task board for development, with automatic git worktree creation for parallel work.

## Overview

This command orchestrates the task selection workflow:
1. Load configuration to identify Notion board and project filter
2. **Query Notion using multi-search strategy** for reliable task discovery
3. Verify and filter tasks by fetching actual properties
4. Present prioritized options based on priority and due date
5. Create git worktree and branch for selected task
6. Load task requirements for development

### Search Reliability

This command uses a **multi-search strategy** to overcome limitations of Notion's semantic search:
- Executes 3 different search queries with varied formulations
- Deduplicates results across all searches
- Fetches each task to verify actual Workstream and Status values
- Filters to show only actionable tasks matching the configured project

## Configuration

### Loading Configuration

Read configuration from two sources:

1. **Global config** at `~/.claude/dev-workflows.local.md`:
   - `notion_sprint_board_id` - Notion database ID for task board
   - `notion_sprint_data_source` - Data source collection URL
   - `slack_channel_id` - Default Slack channel for notifications
   - `worktree_base_path` - Base directory for worktrees (default: `~/worktrees`)

2. **Per-repo config** at `<repo>/.claude/dev-workflows.local.md`:
   - `notion_project_filter` - Project name to filter tasks (e.g., "Project Alpha")
   - `gitlab_project_id` - GitLab project path (e.g., "group/project-name")
   - Can override global settings

### Auto-Detection Fallback

If no per-repo config exists, detect project name from:
1. Git remote URL: `git remote get-url origin` → extract project name
2. Current directory name as fallback

## Workflow

### Step 1: Load Configuration

```bash
# Load global config
cat ~/.claude/dev-workflows.local.md

# Check for per-repo config (overrides)
cat .claude/dev-workflows.local.md 2>/dev/null

# Auto-detect project if needed
git remote get-url origin 2>/dev/null || basename "$PWD"
```

Parse YAML frontmatter to extract configuration values.

Key config values:
- `notion_project_filter` - The workstream name to filter tasks (e.g., "Project Alpha")
- `notion_sprint_data_source` - The Tasks data source URL

### Step 2: Query Notion Task Board

**IMPORTANT**: The Tasks data source has a `Workstream` select property that should be used for filtering. This is more reliable than searching by the `Project` relation field.

#### Multi-Search Strategy

Semantic search can miss tasks due to relevance ranking and result limits. To improve reliability, execute **multiple searches with varied queries** and merge the results.

**Why multiple searches?**
- Semantic search ranks results by relevance to query terms
- A single query may rank some valid tasks lower, causing them to be omitted
- Different query formulations surface different results
- Combining results provides better coverage

#### Search Queries to Execute

Run ALL of the following searches against the Tasks data source (`notion_sprint_data_source`):

1. **Workstream-focused query:**
   ```
   Query: "{notion_project_filter}"
   data_source_url: {notion_sprint_data_source}
   ```

2. **Status-focused query:**
   ```
   Query: "{notion_project_filter} To Do In Progress"
   data_source_url: {notion_sprint_data_source}
   ```

3. **Workstream property query:**
   ```
   Query: "Workstream {notion_project_filter}"
   data_source_url: {notion_sprint_data_source}
   ```

Example for Project Alpha:
```python
searches = [
    "Project Alpha",
    "Project Alpha To Do In Progress",
    "Workstream Project Alpha"
]
data_source = "{notion_sprint_data_source}"
```

#### Deduplication

After running all searches, deduplicate results by task ID:
- Extract the `id` field from each search result
- Keep only unique task IDs
- This prevents showing the same task multiple times

#### Verification Step (Critical)

**Do not trust search highlights alone.** For each unique task ID from the combined search results:

1. **Fetch the full task** using `mcp__plugin_Notion_notion__notion-fetch` with the task ID
2. **Check the actual Workstream property** in the fetched task's properties
3. **Check the actual Status property** to confirm it's actionable

This verification step ensures accuracy because:
- Search highlights may be truncated or misleading
- The actual property values are authoritative
- Tasks from other workstreams that mention the target workstream in content will be filtered out

#### Filtering Criteria

After fetching each task, include it only if:
1. **Workstream** matches `notion_project_filter` exactly
2. **Status** is one of: `To Do`, `In Progress`, `Blocked`, `In Review`
3. **Status** is NOT: `Done`

#### Sort Order

After filtering, sort tasks by:
1. **Priority** (Critical > High > Medium > Low > Backlog)
2. **Due Date** (earliest first, tasks without due dates last)

#### Performance Consideration

While fetching each task adds overhead, it ensures reliable results. For typical task boards with <50 tasks, this is acceptable. The searches can be run in parallel to reduce latency.

### Step 3: Present Task Options

Display tasks in a clear, prioritized format:

```
## Tasks for [Project Name]

### High Priority (Due Soon)
1. [P0] Task title - Due: Jan 8
   ID: abc123 | Status: To Do

2. [P1] Another task - Due: Jan 9
   ID: def456 | Status: In Progress

### Other Tasks
3. [P2] Lower priority task - No due date
   ID: ghi789 | Status: Backlog
```

Ask user which task to work on using `AskUserQuestion` tool.

### Step 4: Set Up Worktree

After task selection, create isolated development environment:

```bash
# Determine worktree path
WORKTREE_BASE="${worktree_base_path:-$HOME/worktrees}"
BRANCH_NAME="feature/task-${TASK_ID}-${TASK_SLUG}"
WORKTREE_PATH="$WORKTREE_BASE/$BRANCH_NAME"

# Ensure we're in git repo root
cd "$(git rev-parse --show-toplevel)"

# Fetch latest
git fetch origin

# Create worktree with new branch from main/master
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@')
git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "origin/$DEFAULT_BRANCH"
```

### Step 5: Load Task Requirements

Fetch full task details from Notion using `mcp__plugin_Notion_notion__notion-fetch` with the task page ID.

Extract and display:
- Task title and description
- Acceptance criteria
- Technical requirements
- Related links or references

### Step 6: Transition to Development

Inform user of setup completion:

```
## Task Ready for Development

**Task:** [Task Title]
**Branch:** feature/task-abc123-task-slug
**Worktree:** /home/user/worktrees/feature/task-abc123-task-slug

### Requirements
[Task description and requirements from Notion]

### Next Steps
To start development, either:
1. Continue here - I'll work in the worktree path
2. Open new terminal in the worktree directory

Say "develop this task" to begin implementation.
```

## Task Slug Generation

Create URL-safe slugs from task titles:
- Lowercase
- Replace spaces with hyphens
- Remove special characters
- Truncate to 30 characters

Example: "Add User Authentication" → "add-user-authentication"

## Handling Edge Cases

### No Tasks Found
If no tasks match the project filter after multi-search:
- Confirm the `notion_project_filter` value matches the Workstream option exactly (case-sensitive)
- Run a broader search without the workstream filter to see all tasks
- Check if tasks exist but are all marked as Done
- Suggest checking Notion board directly via the URL

### Worktree Already Exists
If branch/worktree already exists:
- Offer to switch to existing worktree
- Or create with incremented suffix (e.g., `-v2`)

### No Git Repository
If not in a git repository:
- Cannot create worktree
- Inform user and suggest cloning repo first

## Integration Points

- **Notion MCP**: Fetch task board, query tasks, read task details
- **Git**: Create worktrees, branches, fetch from origin
- **task-development skill**: Hand off after setup for implementation
