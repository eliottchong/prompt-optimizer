# Prompt Optimizer

Small toolkit that **normalizes and lightly structures** raw prompt text: whitespace, long-sentence breaks, bullet prefixes, spelled-out numbers, and common filler phrases. Also estimates the 'before-and-after' token count of raw prompt compared to cleaned prompt. Includes a **CLI** and a **local web dashboard** backed by the same Python function.

> This is heuristic cleanup, not an LLM rewrite. Review output before production use.

## Requirements

- **Python 3.9+**

No third-party packages are required for the current CLI or dashboard server.

## CLI

From this directory:

```bash
python prompt_optimizer.py
```

Paste a prompt, then end input (Ctrl+Z + Enter on Windows, Ctrl+D on Unix).

Or pass a file:

```bash
python prompt_optimizer.py path/to/prompt.txt
```

## Web dashboard

Start the local server (stdlib WSGI):

```bash
python server.py
```

Open **http://127.0.0.1:8765/** in your browser. Optional port:

```bash
python server.py 9000
```

The page calls `POST /api/optimize` with JSON `{"prompt": "..."}` and displays `output` from `clean_prompt()`.

## Project layout

| Path | Purpose |
|------|---------|
| `prompt_optimizer.py` | `clean_prompt()` and CLI |
| `server.py` | Serves `static/dashboard.html` and `/api/optimize` |
| `static/dashboard.html` | Browser UI |
| `PROJECT_STRUCTURE.md` | Planned growth and pipeline notes |

## License

See [LICENSE](LICENSE) (MIT).
