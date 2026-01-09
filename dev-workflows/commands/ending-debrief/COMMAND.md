---
name: Ending Debrief
description: Summarize the day's accomplishments by querying Notion and GitLab, then posting to the daily Slack thread.
---

# Ending Debrief

Summarize the day's accomplishments by querying Notion and GitLab, then posting to the daily Slack thread.

## Overview

This command aggregates work completed across all projects/repos:
1. Query Notion for tasks updated today
2. Query GitLab for MRs created today
3. Correlate and summarize accomplishments
4. Post summary to daily Slack thread

## Data Sources

Unlike other commands that operate within a single conversation, this command queries external systems for the source of truth:

| Source | What to Query |
|--------|---------------|
| **Notion** | Tasks where status changed to "Done"/"In Review" today |
| **GitLab** | MRs created today by the user |
| **Slack** | Today's check-in thread (for posting) |

## Workflow

### Step 1: Load Configuration

Read global config for:
- `notion_sprint_board_id`
- `slack_channel_id`
- `gitlab_group` (optional, for filtering MRs)

### Step 2: Query Notion for Completed Tasks

Use `mcp__plugin_Notion_notion__notion-search` to find tasks for the current workstream:

```
Search parameters:
- query: "Workstream: {notion_project_filter}" (e.g., "Workstream: Project Alpha")
- data_source_url: collection URL from task board (notion_sprint_data_source)
```

**Filter results by:**
- `Workstream` property matches `notion_project_filter` (check search highlights)
- Status is "Done", "In Review", or "In Progress" (work may have been done)

Then fetch each matching task to check:
- Status changed to "Done" or "In Review" today
- Last modified date is today
- Has MR link (indicates work was done)

**Collect for each completed task:**
- Task title
- Task ID/URL
- Status
- MR link (if present)
- Project name

### Step 3: Query GitLab for MRs Created Today

Use `mcp__plugin_gitlab_gitlab__list_merge_requests` to find today's MRs:

```
Parameters:
- created_after: today's date (ISO 8601)
- author_username: current user (if known)
- state: "opened" or "all"
```

**Collect for each MR:**
- MR title
- MR URL
- Project
- Source branch
- Status (open, merged)

### Step 4: Correlate Data

Match MRs to Notion tasks:
- By MR URL in task properties
- By branch name containing task ID
- By title similarity

Create unified list of accomplishments:
```
[
  {
    task_title: "User Authentication",
    task_url: "notion.so/...",
    mr_title: "feat: Add user authentication",
    mr_url: "gitlab.com/.../merge_requests/142",
    mr_status: "open",
    project: "project-alpha"
  },
  ...
]
```

### Step 5: Find Daily Slack Thread

Locate today's check-in thread:

```
Use mcp__slack__slack_get_channel_history
Find message matching ":sunrise: Daily Check-in - {today's date}"
Extract thread_ts
```

### Step 6: Post Ending Debrief Summary

Post summary as reply to daily thread:

```
mcp__slack__slack_reply_to_thread with:
- channel_id: slack_channel_id
- thread_ts: from check-in message
- text: formatted debrief summary
```

**Debrief message format:**
```
:crescent_moon: *Ending Debrief*

*Completed Today:* {count} tasks

:white_check_mark: *User Authentication*
   MR: !142 (ready for review)
   Task: notion.so/abc123

:white_check_mark: *Fix Checkout Bug*
   MR: !143 (ready for review)
   Task: notion.so/def456

*Progress:* 9/12 tasks (75%)
*MRs Opened:* 2
*MRs Merged:* 0

Great work today! :tada:
```

### Step 7: Display Local Summary

Show summary in terminal as well:

```
## Ending Debrief - January 7, 2026

### Completed Tasks (2)

1. **User Authentication**
   - MR: !142 - Ready for review
   - Task: https://notion.so/abc123

2. **Fix Checkout Bug**
   - MR: !143 - Ready for review
   - Task: https://notion.so/def456

### Progress Status
- Completed: 9/12 tasks (75%)
- Remaining: 3 tasks
- Days left: 4

### Posted to Slack
Summary posted to #{channel_name} thread

See you tomorrow!
```

## Multi-Project Summary

When working across multiple projects:

**Group by project:**
```
:crescent_moon: *Ending Debrief*

*Project Alpha:*
:white_check_mark: User Authentication - MR !142

*Project Beta:*
:white_check_mark: Update API docs - MR !87
:white_check_mark: Fix mobile layout - MR !88

*Total:* 3 tasks completed
```

## Handling Edge Cases

### No Work Completed Today
```
:crescent_moon: *Ending Debrief*

No tasks completed today.

*In Progress:*
• User Authentication (50% complete)

*Progress:* 7/12 tasks (58%)

Tomorrow's another day! :muscle:
```

### No Daily Thread Found
- Create new message (not threaded)
- Note that check-in wasn't posted today
- Suggest starting with starting-check-in tomorrow

### Notion/GitLab Query Fails
- Report partial data available
- Note which source failed
- Provide what information is available

### Tasks Without MRs
Include tasks that changed status but have no MR:
```
:white_check_mark: Documentation update (no MR - direct edit)
```

## Date Handling

**Today's date boundaries:**
- Start: 00:00:00 local time
- End: 23:59:59 local time

**ISO 8601 format for APIs:**
```
2026-01-07T00:00:00Z (start)
2026-01-08T00:00:00Z (end, exclusive)
```

**Display format:**
"January 7, 2026"

## Integration Points

- **Notion MCP**: Query tasks updated today
- **GitLab MCP**: Query MRs created today
- **Slack MCP**: Find thread, post summary
- **starting-check-in command**: Creates the thread this command posts to
