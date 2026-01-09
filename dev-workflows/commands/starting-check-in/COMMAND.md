---
name: Starting Check-in
description: Start the workday by creating a daily Slack thread with task overview and priorities across all projects.
---

# Starting Check-in

Start the workday by creating a daily Slack thread with task overview and task priorities across ALL projects.

## Overview

This command creates a structured daily thread in Slack that serves as the hub for all work updates throughout the day. Task completions and ending debriefs reply to this thread.

**Key Features:**
- Covers ALL projects in your Task Tracker
- Prioritizes tasks by Due Date first, then Priority level
- Groups tasks by project for clear organization
- Uses consistent message template for all check-ins

## Constants

- **Thread identifier pattern:** `:sunrise: *Daily Check-in - {Month Day, Year}*`
- **Date format for matching:** Full month name, e.g., "January 8, 2026"
- **Max message length:** 4000 characters (Slack limit)

## Slack Message Template

The check-in follows this **exact template** for consistency:

```
:sunrise: *Daily Check-in - {Month Day, Year}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:chart_with_upwards_trend: *Task Overview*
• Total Active Tasks: {count}
• Completed: {completed}/{total} ({percentage}%)
• Overdue: {overdue_count}
• Blocked: {blocked_count}
• Due Today: {due_today_count}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{overdue_section}

{blocked_section}

:dart: *Today's Priorities*
{prioritized_tasks_by_project}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:rocket: Let's make it happen!
```

### Overdue Section (only if overdue tasks exist)
```
:rotating_light: *OVERDUE*
:file_folder: *{project_name}*
  • [{priority}] {task_name} - Was due {date}

```

### Blocked Section (only if blocked tasks exist)
```
:no_entry: *BLOCKED*
:file_folder: *{project_name}*
  • [{priority}] {task_name}

```

### Tasks By Project Section
```
:file_folder: *{Project Name}*
  • [{priority}] {task_name} - Due: {date}
  • [{priority}] {task_name} - Due: {date}

:file_folder: *{Another Project}*
  • [{priority}] {task_name} - Due: {date}
```

## Workflow

### Step 1: Load Configuration

Read global config from `~/.claude/dev-workflows.local.md`:
```yaml
notion_sprint_board_id: "{your_database_id}"
notion_sprint_data_source: "{your_data_source}"
slack_channel_id: "{your_channel_id}"
notion_priorities: ["Critical", "High", "Medium", "Low", "Backlog"]
```

**Important:** This command queries ALL projects, not just the current repo's project filter.

### Step 2: Query ALL Projects from Notion

First, fetch your Task Tracker database to get all active projects:

```
Use mcp__plugin_Notion_notion__notion-search:
- data_source_url: "{notion_projects_data_source}"
- query: "Status In Progress" or similar to get active projects
```

Then fetch all tasks across all projects:

```
Use mcp__plugin_Notion_notion__notion-search:
- data_source_url: "{notion_sprint_data_source}"
- query: tasks not Done
```

For each task returned, extract:
- Task title
- Status (To Do, In Progress, Blocked, In Review, Done)
- Priority (Critical, High, Medium, Low, Backlog)
- Due Date
- Project (relation to Projects data source)
- Workstream (select property - useful for filtering specific projects)
- Is Epic flag (exclude epics from task list, they're containers)

### Step 3: Calculate Metrics

**Overall metrics:**
- Total active tasks (exclude Done, exclude Epics)
- Completed tasks (Done status)
- Overdue tasks (Due Date < today AND status != Done)
- Tasks due today

**Per-project metrics:**
- Group tasks by Project relation
- Count tasks per project
- Identify project with most urgent items

### Step 4: Sort and Prioritize Tasks

**Primary sort: Due Date**
1. Overdue (past due date, not Done) - HIGHEST
2. Due today
3. Due tomorrow
4. Due this week (within next 7 calendar days)
5. Due later (more than 7 days out)
6. No due date (sorted last)

**Secondary sort (within same due date): Priority**
1. Critical
2. High
3. Medium
4. Low
5. Backlog

**Tertiary sort: Alphabetical by task name**

**Priority display mapping:**
- Critical → `[P0]`
- High → `[P1]`
- Medium → `[P2]`
- Low → `[P3]`
- Backlog → `[--]`

### Step 5: Build Message Using Template

Construct the Slack message following the exact template above.

**Date formatting:**
- Header date: "January 8, 2026" (full month name)
- Task due dates: "Jan 8" (abbreviated) or "Today", "Tomorrow", "Overdue"

**Project grouping rules:**
1. Only show projects that have active (non-Done) tasks
2. Order projects by urgency (project with most overdue/due-today tasks first)
3. Within each project, show max 5 tasks (top priority)
4. Add "(+N more)" if project has additional tasks

**Example grouped output:**
```
:file_folder: *Project Alpha*
  • [P0] Orchestration - Deploy components - Due: Today
  • [P1] API Integration - Run test suite - Due: Jan 10
  (+3 more tasks)

:file_folder: *Project Beta*
  • [P0] Test Infrastructure Plugin - Due: Jan 9
  • [P0] Clean up documentation - Due: Today
```

### Step 6: Post to Slack

Use `mcp__slack__slack_post_message`:
```json
{
  "channel_id": "{slack_channel_id}",
  "text": "{formatted_message}"
}
```

**Important:** Save the returned `ts` (timestamp) value - this identifies the thread for subsequent replies throughout the day.

**Thread Tracking:**
The thread timestamp is used by other skills (task-completion, ending-debrief) to post replies. These will search channel history to find today's thread, so persistent storage of the `ts` is optional. However, informing the user of the timestamp in the local summary can help with debugging.

### Step 7: Display Local Summary

After posting, show in terminal:

```
## Daily Check-in Posted

Posted to #{channel_name} at {time}

### Task Overview
- Active Tasks: {count} across {project_count} projects
- Overdue: {overdue_count}
- Due Today: {due_today_count}

### Top Priorities (All Projects)
1. [P0] {task} ({project}) - Due today
2. [P0] {task} ({project}) - Due today
3. [P1] {task} ({project}) - Due tomorrow

Say "what should I work on" to pick a task, or specify a project to filter.
```

## Finding Today's Thread

Other skills/commands need to find today's thread to post replies.

**Search method:**
1. Use `mcp__slack__slack_get_channel_history` to get recent messages
2. Look for message matching pattern: `:sunrise: *Daily Check-in - {today's date}*`
3. Extract the message's `ts` for thread replies

**Date format for matching:** "January 8, 2026" (full month name, day, year)

**Note:** The thread identifier pattern `:sunrise: *Daily Check-in -` is shared across all dev-workflows commands/skills (starting-check-in, task-completion, ending-debrief) to ensure consistent thread linking.

## Handling Edge Cases

### No Active Tasks in Any Project
```
:sunrise: *Daily Check-in - January 8, 2026*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:tada: *All Clear!*

No active tasks across any project.
Time to plan the next cycle or pick up new work!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:coffee: Enjoy a well-deserved break!
```

### Slack Channel Not Configured
- Display check-in locally in terminal only
- Prompt user to configure Slack channel in `~/.claude/dev-workflows.local.md`

### Already Posted Today
If a check-in thread exists for today:
1. Inform user check-in already posted
2. Show link to existing thread
3. Offer to post a "refresh update" as a reply to the thread instead

### Project Has No Name
If a task's Project relation is empty or unresolved:
- Group under "*Unassigned Project*"

### Tasks with No Priority Set
- Default to display as `[--]` (lowest priority in sort)

### Tasks with No Due Date
- Display as "Due: Not set"
- Sort after all tasks with due dates
- Within no-due-date tasks, sort by Priority then alphabetically

### Blocked Tasks
If tasks have "Blocked" status, add a section after Overdue:
```
:no_entry: *BLOCKED*
:file_folder: *{Project Name}*
  • [{priority}] {task_name} - Blocked since {status_change_date}
```

### Notion API Failures
If the Notion query fails or times out:
- Display error message to user
- Suggest retrying or checking Notion connectivity
- Do NOT post to Slack with incomplete data

### Large Number of Tasks
If total tasks exceed 50:
- Still show all projects, but limit to top 3 tasks per project
- Add "(+N more tasks)" indicator for each project
- Include total count in Task Overview section
- Keep message under 4000 character Slack limit

### Validation Before Posting
Before posting to Slack, verify:
- [ ] Message length < 4000 characters
- [ ] At least one task OR "No active tasks" message present
- [ ] No empty project sections
- [ ] All project names resolved (no orphan tasks)

## Data Source Reference

**Task Tracker Database:** `{your_database_id}`

| Data Source | Collection ID | Purpose |
|------------|---------------|---------|
| Projects | `{notion_projects_data_source}` | Project metadata |
| Tasks | `{notion_sprint_data_source}` | Individual tasks |

**Tasks Schema:**
- `Task` (title) - Task name
- `Status` - To Do, In Progress, Blocked, In Review, Done
- `Priority` - Critical, High, Medium, Low, Backlog
- `Due Date` - Date property
- `Project` - Relation to Projects data source
- `Is Epic` - Checkbox (exclude if true)

## Integration Points

- **Notion MCP**: Query both Projects and Tasks data sources
- **Slack MCP**: Post check-in message, create thread
- **task-completion skill**: Posts task completion replies to this thread
- **ending-debrief command**: Posts daily summary to this thread
