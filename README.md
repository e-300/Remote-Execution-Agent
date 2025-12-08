

## Project Architecture

```
          ┌─────────────────────────────────────────────────────────────────────────────┐
          │                                 Tailnet                                     │
          │                                                                             │
          │  ┌──────────────┐         ┌─────────────────────┐         ┌──────────────┐  │
          │  │    Local     │ ◄──────►│       Agent         │ ◄──────►│Remote Server │  │
          │  │              │   HTTP  │   (self-hosted)     │   SSH   │              │  │
          │  └──────────────┘         │                     │         │ Executes:    │  │
          │                           │  - Web UI           │         │  df -h       │  │
          │                           │  - MCP tools        │         │  free -m     │  │
          │                           │  - SSH client       │         │  systemctl   │  │
          │                           └──────────┬──────────┘         └──────────────┘  │
          │                                      │                                      │
          └──────────────────────────────────────┼───────────────────────────────────── ┘
                                                 │
                                                 │ HTTPS (API call)
                                                 ▼
                                         ┌──────────────────┐
                                         │  Anthropic API   │
                                         │                  │
                                         └──────────────────┘
                    
```
# Project is under Devlopment!
Estimated date of completion is Dec 10th 2025!

# Tailscale-Secured-Remote-Node-Execution-Agent-with-MCP

A proof-of-concept agent that lets you chat with Claude to execute commands on a remote server via SSH and Tailscale, using the Model Context Protocol (MCP).

## What This Does

Chat with Claude through a local Gradio UI. Claude can execute whitelisted commands on your remote server and return real results. The whole thing is wired together with MCP for clean tool definitions.

## Project Phases

### Phase 1: Foundation
**Milestone: "Hello Claude"**
1. Set up project directory structure
2. Create virtual environment
3. Install core dependencies (gradio, anthropic, asyncssh, pydantic, mcp)
4. Create a basic Gradio chat UI that echoes messages back
5. Integrate Claude API - get a simple conversation working
6. Verify you can chat with Claude through your local Gradio interface

### Phase 2: MCP Server Basics
**Milestone: "MCP Server Runs"**
1. Understand MCP server structure (tools, resources, prompts)
2. Create MCP server entry point
3. Define a dummy tool (e.g., `ping` that returns "pong")
4. Test MCP server standalone using MCP inspector or CLI
5. Verify the server starts and exposes tools correctly

### Phase 3: Remote Connection
**Milestone: "SSH Works"**
1. Create a config file schema (Pydantic) for remote server details
2. Build a standalone SSH utility module
3. Test manual SSH command execution to your remote server
4. Handle SSH authentication (key-based recommended)
5. Add error handling for connection failures, timeouts
6. Verify you can run `whoami` on the remote server programmatically

### Phase 4: MCP Tools Definition
**Milestone: "Real Tools Defined"**
1. Define your command whitelist as Pydantic enums/models
2. Create parameter schemas with validation
3. Implement MCP tools that wrap your SSH utility
4. Register each tool with proper descriptions (Claude reads these)
5. Test tools via MCP inspector - verify inputs validate correctly
6. Verify tool execution returns real data from remote server

### Phase 5: MCP Client Integration
**Milestone: "Agent Speaks MCP"**
1. Build MCP client into your agent
2. Connect client to your MCP server (stdio or HTTP transport)
3. Fetch available tools from MCP server
4. Convert MCP tool definitions to Claude API tool format
5. Verify agent can discover tools dynamically

### Phase 6: Tool Execution Loop
**Milestone: "End-to-End Works"**
1. Wire together: Gradio UI → Claude API → MCP Client → MCP Server → SSH → Response
2. Implement the agentic loop:
   - User message → Claude
   - Claude returns tool_use → MCP client executes via MCP server
   - Tool result → back to Claude
   - Claude returns final response → UI
3. Handle multi-step tool calls (Claude may call several tools)
4. Add conversation history management
5. Test full flow: ask Claude to check disk space, see real results

### Phase 7: Configuration & UX
**Milestone: "User Can Configure"**
1. Create config file or env vars for remote server IP (Tailscale IP)
2. Add startup validation (MCP server healthy? SSH reachable?)
3. Display connection status in UI
4. Add graceful error messages when things fail
5. Document setup steps for a new user

### Phase 8: Security Hardening
**Milestone: "Safe for Demo"**
1. Audit command whitelist - remove anything dangerous
2. Add input sanitization on parameterized commands
3. Implement rate limiting or confirmation for destructive commands
4. Add logging for all executed commands (MCP server side)
5. Review SSH key permissions and access scope

### Phase 9: Polish (Optional)
**Milestone: "Looks Legit"**
1. Add Tailscale setup instructions to README
2. Create a simple startup script (launches MCP server + agent)
3. Add example commands to UI welcome message
4. Test on fresh machine to verify docs are accurate

## Quick Test

1. Start the MCP server + agent
2. Open the Gradio UI
3. Connect to your remote server
4. Ask Claude to check server status
5. See real data from your remote server in the chat
6. Add a new whitelisted command by editing one file
