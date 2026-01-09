---
name: Task Completion
description: This skill should be used when the user says "I'm done", "task complete", "ready for review", "finish this task", "complete this task", "ship it", or has finished development and wants to commit, create MR, update Notion, and post to Slack. Handles the full completion workflow including git operations, merge request creation, cross-platform notifications, and worktree cleanup.
---

# Task Completion

Complete a developed task by committing, creating MR, updating Notion, posting to the daily Slack thread, and cleaning up the worktree.

## Overview

This skill handles the post-development workflow:
1. Verify readiness and detect worktree status
2. Commit, push, and create merge request (via `/commit-push-mr` or manual steps)
3. Post update to daily Slack thread
4. Update Notion task with MR link and status
5. Clean up git worktree and return to main repo

## Prerequisites

Before completion:
- Development complete and validated
- Changes staged (or ready to stage)
- Tests passing
- In correct worktree/branch

## Workflow

### Step 1: Verify Readiness

Confirm development state and detect worktree:

```bash
# Verify branch
BRANCH_NAME=$(git branch --show-current)
echo "Current branch: $BRANCH_NAME"

# Check for uncommitted changes
git status

# Detect if in worktree
TOPLEVEL=$(git rev-parse --show-toplevel)
MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
if [ "$TOPLEVEL" != "$MAIN_REPO" ]; then
    IS_WORKTREE=true
    WORKTREE_PATH="$TOPLEVEL"
    echo "Working in worktree: $WORKTREE_PATH"
    echo "Main repo: $MAIN_REPO"
else
    IS_WORKTREE=false
    echo "Working in main repository (no worktree)"
fi

# Verify tests pass (if not already run)
npm test || pytest || go test ./... || echo "Verify tests manually"
```

**Capture these values for later steps:**
- `BRANCH_NAME` - Current branch name
- `IS_WORKTREE` - Whether we're in a worktree
- `WORKTREE_PATH` - Path to current worktree (if applicable)
- `MAIN_REPO` - Path to main repository

### Steps 2-4: Commit, Push, and Create MR

**Option A: Use the `/commit-push-mr` command (Recommended)**

The commit-commands plugin provides a streamlined command that handles commit, push, and MR creation in one step:

```
/commit-push-mr
```

This command will:
- Analyze the current changes
- Create a commit with appropriate message
- Push to origin
- Create a merge request on GitLab

**Option B: Manual steps**

If more control is needed, perform each step manually:

**Step 2: Commit Changes**
```bash
# Stage all changes
git add -A

# Create commit
git commit -m "$(cat <<'EOF'
feat: [Task Title]

[Brief description of what was implemented]

- [Key change 1]
- [Key change 2]
- [Key change 3]

Task: [Notion task URL]

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Commit message format:**
- Type prefix: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- Short title (50 chars)
- Blank line
- Description body
- Task reference
- Co-author attribution

**Step 3: Push to Remote**
```bash
git push -u origin "$(git branch --show-current)"
```

**Step 4: Create Merge Request**
```
mcp__plugin_gitlab_gitlab__create_merge_request with:
- project_id: from config (gitlab_project_id)
- source_branch: current branch
- target_branch: main (or from config)
- title: "feat: [Task Title]"
- description: formatted MR description
```

**MR description format:**
```markdown
## Summary
[Brief description of changes]

## Changes
- [Key change 1]
- [Key change 2]

## Testing
- [x] Unit tests added/updated
- [x] All tests passing
- [x] Manual testing completed

## Notion Task
[Link to Notion task]

---
:robot: Generated with Claude Code
```

**Capture the MR URL** from the response for subsequent steps.

### Step 3: Post to Daily Slack Thread

Find today's check-in thread and post update:

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
- text: formatted completion message
```

**Slack message format:**
```
:white_check_mark: *MR Opened:* [Task Title]

*Branch:* `feature/task-abc123-slug`
*MR:* [GitLab MR URL]
*Task:* [Notion task URL]

Changes:
• [Brief change summary]
```

**Fallback if no thread found:**
- Post as new message (not reply)
- Note that daily thread wasn't found

### Step 4: Update Notion Task

Update the task in Notion with completion info:

```
mcp__plugin_Notion_notion__notion-update-page with:
- page_id: task page ID
- command: "update_properties"
- properties:
  - Status: "In Review" (or configured status)
  - MR Link: GitLab MR URL
```

Also add work summary to task content:

```
mcp__plugin_Notion_notion__notion-update-page with:
- page_id: task page ID
- command: "insert_content_after"
- selection_with_ellipsis: (end of existing content)
- new_str: work summary section
```

**Work summary format:**
```markdown
---
## Development Summary (Jan 7, 2026)

**MR:** [GitLab MR URL]
**Branch:** feature/task-abc123-slug

### Changes Made
- Created login component with JWT handling
- Added auth middleware to API routes
- Implemented refresh token rotation

### Files Modified
- `src/auth/login.ts` (new)
- `src/api/routes.ts` (modified)
- `tests/auth.test.ts` (new)
```

### Step 5: Worktree Cleanup

If working in a worktree (detected in Step 1), clean it up and return to main repo:

```bash
# Only if IS_WORKTREE is true
if [ "$IS_WORKTREE" = true ]; then
    echo "Cleaning up worktree..."

    # IMPORTANT: Navigate to main repo BEFORE removing worktree
    # You cannot remove a worktree while your shell is inside it
    cd "$MAIN_REPO"

    # Remove the worktree (with error handling)
    if git worktree remove "$WORKTREE_PATH"; then
        echo "Worktree removed successfully"
    else
        echo "Warning: Worktree removal failed. Manual cleanup may be needed."
        echo "Run: git worktree remove --force $WORKTREE_PATH"
    fi

    # Prune any stale worktree references
    git worktree prune

    # Optionally delete the local branch (it's now on remote via push)
    # Only do this after MR is created
    git branch -d "$BRANCH_NAME" 2>/dev/null || true

    echo "Worktree cleaned up. Now in main repo: $MAIN_REPO"
else
    echo "Not in a worktree - no cleanup needed"
fi
```

**Important safety notes:**
- Always navigate OUT of the worktree before removing it
- Use `git worktree remove` (not `rm -rf`) to properly unregister
- Branch deletion is safe because changes are pushed to remote
- If removal fails, provide manual cleanup instructions but continue workflow

### Completion Summary

Display final summary to user:

```
## Task Completed :white_check_mark:

**Task:** [Task Title]
**Branch:** feature/task-abc123-slug

### Actions Taken
- [x] Committed changes: abc1234
- [x] Pushed to origin
- [x] Created MR: !142
- [x] Posted to Slack thread
- [x] Updated Notion task
- [x] Cleaned up worktree (if applicable)

### Links
- **MR:** https://gitlab.com/group/project/-/merge_requests/142
- **Notion:** https://notion.so/task/abc123
- **Slack:** #{channel_name} thread

### Current Location
Returned to main repository: {main_repo_path}

### Next Steps
- MR ready for review
- Say "what should I work on" for next task
```

## Configuration Requirements

Required in config files:
- `slack_channel_id` - For thread posting
- `gitlab_project_id` - For MR creation
- `notion_sprint_board_id` - For task lookup

Optional:
- `default_target_branch` - MR target (default: main)
- `status_in_review` - Notion status value (default: "In Review")

## Handling Edge Cases

### No Daily Thread Found
- Post as standalone message
- Include note that check-in wasn't found
- Still complete other steps

### MR Creation Fails
- Display error
- Provide manual MR creation instructions
- Continue with other notifications

### Notion Update Fails
- Display error
- Provide manual update instructions
- Complete Slack notification

### Branch Already Has MR
- Detect existing MR for branch
- Update existing MR instead of creating new
- Or inform user and skip MR step

### Worktree Cleanup Fails
If `git worktree remove` fails (e.g., uncommitted changes, locked files):
- Display warning with error details
- Provide manual cleanup instructions:
  ```bash
  cd [main_repo_path]
  git worktree remove --force [worktree_path]
  git worktree prune
  ```
- Continue with completion summary (MR and notifications still succeeded)
- Do not fail the entire completion workflow

### Not in a Worktree
If working directly in main repository (not a worktree):
- Skip worktree detection and cleanup steps gracefully
- Note in completion summary: "No worktree cleanup needed"
- All other steps proceed normally

### Worktree Has Uncommitted Changes
Should not happen if Step 2 (Commit) succeeded, but if detected:
- Warn user about uncommitted changes
- Offer to commit them before cleanup
- Or skip cleanup and preserve worktree

## Integration Points

- **Git**: Commit, push, worktree management operations
- **GitLab MCP**: Create/update merge requests
- **Slack MCP**: Find thread, post replies
- **Notion MCP**: Update task properties and content
- **commit-commands plugin**: Can use `/commit-push-mr` as alternative
