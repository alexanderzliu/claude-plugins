# Notion MCP Plugin

Custom Notion MCP server providing structured database querying with filters, sorts, and pagination - features not available in other Notion integrations without an Enterprise plan.

## Features

- **Structured Database Queries**: Filter, sort, and paginate database results
- **Full Property Support**: All Notion property types supported (text, select, date, relation, etc.)
- **Page Management**: Create, read, update pages and their content
- **Block Operations**: Append and update content blocks
- **Search**: Search across your entire workspace
- **User Management**: List and get user details

## Installation

1. Install from the plugin marketplace:
   ```
   /install-plugin notion
   ```

2. Set your Notion API key:
   ```bash
   export NOTION_API_KEY="your-notion-integration-token"
   ```

## Getting a Notion API Key

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Give it a name and select the workspace
4. Copy the "Internal Integration Token"
5. **Important**: Share your databases/pages with the integration by clicking "..." → "Connections" → Add your integration

## Available Tools

### Database Operations

#### `notion_query_data_source`
Query a data source with filters, sorts, and pagination. Use `notion_get_database` first to get the `data_source_id`.

```json
{
  "data_source_id": "b21c6b12-d233-...",
  "filter": {
    "and": [
      {"property": "Status", "status": {"equals": "In Progress"}},
      {"property": "Priority", "select": {"equals": "High"}}
    ]
  },
  "sorts": [
    {"property": "Due Date", "direction": "ascending"}
  ],
  "page_size": 50
}
```

**Filter operators by property type:**
| Type | Operators |
|------|-----------|
| Text | `equals`, `does_not_equal`, `contains`, `does_not_contain`, `starts_with`, `ends_with`, `is_empty`, `is_not_empty` |
| Number | `equals`, `does_not_equal`, `greater_than`, `greater_than_or_equal_to`, `less_than`, `less_than_or_equal_to` |
| Select/Status | `equals`, `does_not_equal`, `is_empty`, `is_not_empty` |
| Multi-select | `contains`, `does_not_contain`, `is_empty`, `is_not_empty` |
| Date | `equals`, `before`, `after`, `on_or_before`, `on_or_after`, `this_week`, `past_week`, `past_month` |
| Checkbox | `equals`, `does_not_equal` |
| Relation | `contains`, `does_not_contain`, `is_empty`, `is_not_empty` |

#### `notion_get_database`
Get database metadata and property schema.

### Page Operations

#### `notion_get_page`
Retrieve a page's properties.

#### `notion_get_page_content`
Get content blocks (paragraphs, headings, lists, etc.).

#### `notion_create_page`
Create a new page in a database or as a child page.

#### `notion_update_page`
Update page properties or archive a page.

### Block Operations

#### `notion_append_blocks`
Append content blocks to a page.

#### `notion_update_block`
Update or archive a block.

### Search

#### `notion_search`
Search across all pages and databases in the workspace.

### Users

#### `notion_list_users`
List all users in the workspace.

#### `notion_get_user`
Get details about a specific user.

## Example Usage

### Query tasks due this week
```
Query the database for tasks where Status is "To Do" and Due Date is this week, sorted by Priority
```

### Create a new page
```
Create a new page in my Tasks database with title "Review PR" and Status "To Do"
```

### Search for content
```
Search Notion for pages containing "quarterly report"
```

## Requirements

- Python 3.10+
- `uv` package manager (for dependency management)
- Notion API key with appropriate permissions

## Troubleshooting

### "Could not find database"
Make sure the database is shared with your integration. Click "..." on the database → "Connections" → Add your integration.

### Rate limiting
Notion API has a rate limit of ~3 requests/second. The server handles this gracefully but very rapid queries may see delays.

### Missing properties
Some property types (like rollups and formulas) are read-only and cannot be set when creating/updating pages.
