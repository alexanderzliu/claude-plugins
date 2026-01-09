---
name: Task Development
description: This skill should be used when the user says "develop this task", "implement the requirements", "work on this task", "start development", "build this feature", or wants to autonomously develop a feature based on Notion task requirements. Orchestrates the full development cycle using feature-dev workflow with code exploration, architecture, implementation, and review.
---

# Task Development

Autonomously develop features based on Notion task requirements using a structured development workflow.

## Overview

This skill orchestrates end-to-end development:
1. Load task requirements from Notion
2. Explore codebase to understand context
3. Design implementation approach
4. Implement the feature
5. Test and validate
6. Prepare for completion

Leverages the existing `/feature-dev` command and its specialized agents (code-explorer, code-architect, code-reviewer).

## Prerequisites

Before starting development:
- Task selected via task-selection command
- Working in correct worktree/branch
- Task requirements available from Notion

## Workflow

### Phase 1: Load Requirements

If task context not already loaded, fetch from Notion:

```
Use mcp__plugin_Notion_notion__notion-fetch with the task page ID to get:
- Task title and description
- Acceptance criteria
- Technical requirements
- Design specifications
- Related links
```

Parse and structure requirements:
- **Goal**: What the feature should accomplish
- **Acceptance Criteria**: Specific conditions for completion
- **Technical Constraints**: Required technologies, patterns, limitations
- **Dependencies**: Related tasks, APIs, or systems

### Phase 2: Codebase Exploration

Launch code-explorer agent (from feature-dev plugin) to understand:
- Existing patterns and conventions
- Related code that will be affected
- Integration points
- Test patterns used in the project

**Key questions to answer:**
- Where does similar functionality exist?
- What patterns should this follow?
- What files need modification?
- What tests exist for related features?

### Phase 3: Architecture Design

Launch code-architect agent to design implementation:
- Identify files to create/modify
- Design component structure
- Plan data flow
- Consider edge cases
- Propose implementation sequence

**Output:** Clear implementation plan with:
- Ordered list of changes
- File paths and modifications
- New files to create
- Test approach

### Phase 4: Implementation

Execute the implementation plan:

1. **Create/modify files** following the architecture design
2. **Follow existing patterns** discovered during exploration
3. **Write tests** alongside implementation
4. **Commit incrementally** for complex changes (optional)

**Implementation principles:**
- Match existing code style
- Add appropriate error handling
- Include necessary logging
- Write self-documenting code

### Phase 5: Validation

Launch code-reviewer agent to validate:
- Code quality and correctness
- Adherence to requirements
- Test coverage
- Security considerations
- Performance implications

**Run automated checks:**
```bash
# Run project tests
npm test || pytest || go test ./... || (appropriate test command)

# Run linters if configured
npm run lint || flake8 || golint || (appropriate lint command)

# Build to verify no compile errors
npm run build || cargo build || go build || (appropriate build command)
```

### Phase 6: Prepare for Completion

After successful validation:

1. **Summarize work done:**
   - Files created/modified
   - Features implemented
   - Tests added
   - Any deviations from requirements

2. **Stage changes:**
   ```bash
   git add -A
   git status
   ```

3. **Inform user:**
   ```
   ## Development Complete

   **Task:** [Task Title]
   **Branch:** feature/task-abc123-slug

   ### Changes Made
   - Created `src/auth/login.ts` - Login component
   - Modified `src/api/routes.ts` - Added auth endpoints
   - Added `tests/auth.test.ts` - Auth test suite

   ### Test Results
   All 24 tests passing

   ### Ready for Review
   Say "I'm done" or "complete this task" to:
   - Commit and push changes
   - Create merge request
   - Update Notion task
   - Post to Slack
   ```

## Integration with feature-dev

This skill integrates with the existing feature-dev plugin:

**Available agents:**
- `code-explorer` - Traces execution paths, maps architecture
- `code-architect` - Designs implementation blueprints
- `code-reviewer` - Reviews with confidence-based filtering

**Invocation:**
Use the Task tool with appropriate subagent_type:
- `subagent_type: "feature-dev:code-explorer"`
- `subagent_type: "feature-dev:code-architect"`
- `subagent_type: "feature-dev:code-reviewer"`

## Handling Complex Tasks

For large or complex tasks:

1. **Break down into subtasks** using TodoWrite
2. **Implement incrementally** with validation between steps
3. **Commit at milestones** to preserve progress
4. **Update user** on progress throughout

## Error Handling

### Tests Failing
- Analyze failure output
- Fix issues iteratively
- Re-run until passing

### Build Errors
- Read error messages carefully
- Fix compilation/type issues
- Verify imports and dependencies

### Requirements Unclear
- Use AskUserQuestion for clarification
- Document assumptions made
- Note questions for task completion update

## Integration Points

- **Notion MCP**: Load task requirements
- **feature-dev agents**: Exploration, architecture, review
- **Git**: Stage changes, verify branch
- **task-completion skill**: Hand off for commit/MR/notifications
