#!/usr/bin/env bash
# Instagram MCP launcher for Claude Code. cwd = repo root (relative imports + .env).
cd "$(dirname "$0")"
exec .venv/bin/python -m src.instagram_mcp_server
