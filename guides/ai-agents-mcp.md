# Order books from Claude, Cursor and other AI agents (MCP)

InkChamps runs a [Model Context Protocol](https://modelcontextprotocol.io) server, so an AI agent can make a whole book for you: Claude Desktop, Claude Code, Cursor or any MCP client. Every prompt in this library includes the exact call under **Exact settings for AI agents**.

## Connect

1. Sign in to [InkChamps](https://inkchamps.com/?utm_source=github&utm_medium=prompt_library&utm_campaign=ai-coloring-book-prompts&utm_content=guide-mcp) and create an MCP key under **Settings → MCP**.
2. Add the server to your client:

```json
{
  "mcpServers": {
    "inkchamps": {
      "url": "https://prod.api.inkchamps.com/mcp/book-creation",
      "headers": { "Authorization": "Bearer ic_mcp_YOUR_KEY" }
    }
  }
}
```

The key spends your account's credits, so keep it private.

## The tools

| Tool | What it does |
|---|---|
| `list_book_types` | Book types, styles, activities, sizes and credit rates |
| `get_credits` | Your balance, and what an order would cost |
| `create_coloring_book` | A coloring book |
| `create_story_coloring_book` | A coloring book that tells one story |
| `create_illustrated_story_book` | A full-colour picture book |
| `create_activity_book` | Mazes, word search, sudoku, tracing and more |
| `create_educational_coloring_book` | A color-to-learn book |
| `create_cover_photo` | A KDP paperback cover |
| `get_job_status` | Progress, and the PDF link when it is ready |

## Use a prompt from this library

Tell your agent, for example:

```text
Use the InkChamps MCP server to make the "Friendly dinosaurs for preschoolers" book from
https://inkchamps.com/prompts/coloring-books/dinosaur/
Check my credits first, then place the order and send me the PDF link when it is done.
```

Or paste the JSON from a prompt's **Exact settings** section: `tool` is the tool to call and `arguments` are its inputs. For bulk work, [`prompts.json`](../prompts.json) has every prompt's call in one file.

The agent must still ask you for the choices that are yours: the reader's age, Standard or Premium quality, and for activity books the activities, ink and maze styles. The prompts here already state all of them.
