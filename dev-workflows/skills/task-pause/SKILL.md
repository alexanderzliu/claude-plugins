---
name: Task Pause
description: This skill should be used when the user says "pause this task", "save my progress", "stopping for now", "WIP commit", "take a break", "I'll continue later", "park this task", or needs to save progress on a task without completing it. Commits work-in-progress, optionally pushes, posts update to Slack, updates Notion with progress summary, and preserves worktree for later continuation.
---

# Task Pause

Save progress on a task without completing it, preserving the worktree for later continuation.

## Overview

This skill handles pausing an in-progress task:
1. Verify state and uncommitted changes
2. Create WIP commit with progress summary
3. Optionally push branch to remote (for backup)
4. Post progress update to daily Slack thread
5. Update Notion task with progress summary
6. Provide resumption instructions

**Key difference from task-completion:** The worktree is preserved for later continuation.

## Prerequisites

Before pausing:
- Some work has been done on the task
- Changes exist (staged or unstaged)
- Working in correct worktree/branch
- Task context available (Notion task ID, title)

## Workflow

### Step 1: Verify State

Check current development state:

```bash
# Verify branch
BRANCH_NAME=$(git branch --show-current)
echo "Current branch: $BRANCH_NAME"

# Check for uncommitted changes
git status

# Detect worktree info (for resumption instructions)
TOPLEVEL=$(git rev-parse --show-toplevel)
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
if [ "$TOPLEVEL" != "$MAIN_REPO" ]; then
    WORKTREE_PATH="$TOPLEVEL"
    echo "Working in worktree: $WORKTREE_PATH"
else
    WORKTREE_PATH=""
    echo "Working in main repository"
fi
```

**Capture these values:**
- `BRANCH_NAME` - Current branch name
- `WORKTREE_PATH` - Worktree location (for resumption)

### Step 2: WIP Commit

Stage and commit with WIP prefix:

```bash
# Stage all changes
git add -A

# Create WIP commit
git commit -m "$(cat <<'EOF'
WIP: [Task Title] - Progress checkpoint

Work in progress:
- [What has been done so far]
- [Current state]

Next steps:
- [What remains to be done]

Task: [Notion task URL]

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**WIP commit message format:**
- Prefix: `WIP:` to clearly mark as incomplete
- Task title for context
- Brief summary of progress
- Next steps for resumption
- Task reference link

### Step 3: Optional Push

Ask user if they want to push to remote (for backup):

Use `AskUserQuestion` with options:
- **Push to remote (Recommended)** - Backup work to GitLab
- **Keep local only** - Don't push yet

If pushing:
```bash
git push -u origin "$(git branch --show-current)"
```

### Step 4: Post to Daily Slack Thread

Find today's check-in thread and post progress update:

**Find thread:**
```
Use mcp__slack__slack_get_channel_history to get recent messages
Find message matching ":sunrise: Daily Check-in - {today's date}"
Extract the message 'ts' for thread_ts
```

**Post reply:**
```
mcp__slack__slack_reply_to_thread with:
- channel_id: configured slack_channel_id
- thread_ts: from check-in message
- text: formatted progress message
```

**Slack message format:**
```
:pause_button: *Progress Saved:* [Task Title]

*Branch:* `feature/task-abc123-slug`
*Status:* Work in progress (paused)
*Task:* [Notion task URL]

Progress:
- [Summary of work done so far]

Will continue later.
```

**Fallback if no thread found:**
- Post as new message (not reply)
- Note that daily thread wasn't found

### Step 5: Update Notion Task

Add progress summary to task content (do NOT change status):

```
mcp__plugin_Notion_notion__notion-update-page with:
- page_id: task page ID
- command: "insert_content_after"
- selection_with_ellipsis: (end of existing content)
- new_str: progress summary section
```

**Progress summary format:**
```markdown
---
## Progress Update (Jan 8, 2026) - WIP

**Branch:** feature/task-abc123-slug
**Status:** In Progress (paused)

### Work Done
- [Completed item 1]
- [Completed item 2]

### Remaining
- [Todo item 1]
- [Todo item 2]

### Notes
[Any relevant context for resumption]
```

**Important:** Do NOT update the Status property - task remains "In Progress"

### Step 6: Resumption Instructions

Display instructions for continuing later:

```
## Task Paused :pause_button:

**Task:** [Task Title]
**Branch:** feature/task-abc123-slug

### Actions Taken
- [x] Created WIP commit: abc1234
- [x] Pushed to remote (if selected)
- [x] Posted progress to Slack thread
- [x] Updated Notion with progress summary

### Worktree Preserved
Your worktree is preserved at:
`/home/user/worktrees/feature/task-abc123-slug`

### To Resume Later
1. Navigate to the worktree:
   ```bash
   cd /home/user/worktrees/feature/task-abc123-slug
   ```

2. Start Claude Code and say:
   - "continue this task"
   - "resume development"
   - "what was I working on?"

### Links
- **Task:** [Notion task URL]
- **Branch:** feature/task-abc123-slug
```

## Configuration Requirements

Required in config files:
- `slack_channel_id` - For thread posting
- `worktree_base_path` - For resumption instructions

## Handling Edge Cases

### No Changes to Commit
If `git status` shows no changes:
- Skip commit step
- Still post Slack update and update Notion
- Note in summary: "No uncommitted changes"

### No Daily Thread Found
- Post as standalone message
- Include note that check-in wasn't found
- Still complete other steps

### Notion Update Fails
- Display error
- Provide manual update instructions
- Complete Slack notification

### Already Pushed
If branch already has upstream:
- Use `git push` without `-u`
- Note that changes were pushed to existing remote

### On Main/Master Branch
- Warn user they're not on a feature branch
- Suggest creating a branch first
- Or proceed with caution (WIP commit to main is unusual)

### Multiple Pause Operations
If the branch already has WIP commits from previous pauses:
- Create a new WIP commit (don't amend previous)
- Each pause creates a separate checkpoint
- This preserves the development history
- Note previous WIP commits in the summary if desired

## Integration Points

- **Git**: Commit, optionally push (worktree NOT removed)
- **Slack MCP**: Find thread, post progress update
- **Notion MCP**: Update task content (NOT status)
- **AskUserQuestion**: Prompt for push preference

## Comparison with Task Completion

| Aspect | Task Pause | Task Completion |
|--------|------------|-----------------|
| Commit | WIP prefix | feat/fix prefix |
| Push | Optional (ask user) | Always |
| MR | Not created | Created |
| Notion Status | Unchanged | "In Review" |
| Slack Message | Progress update | Completion announcement |
| Worktree | Preserved | Cleaned up |
