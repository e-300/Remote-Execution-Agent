
# Tailscale-Secured Remote Node Execution Agent with MCP

A proof-of-concept agent that lets you chat with Claude to execute commands on a remote server via SSH and Tailscale, using the Model Context Protocol (MCP).

## 🎯 What This Does

Chat with Claude through a local Gradio UI. Claude can execute whitelisted commands on your remote server and return real results. The whole thing is wired together with MCP for clean tool definitions.

**Example conversation:**
```
You: Check the disk space on my server
Claude: [executes df -h via SSH]
       Here's your disk usage:
       - / is 45% full (23GB used of 50GB)
       - /home is 78% full...
```


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


## 🏗️ Project Structure

```
tailscale-mcp-agent/
├── src/
│   ├── __init__.py
│   ├── chat_ui.py        # Gradio chat interface + agentic loop
│   ├── mcp_server.py     # MCP server with tool definitions
│   ├── mcp_client.py     # MCP client for agent
│   ├── ssh_client.py     # SSH command execution
│   └── config.py         # Configuration models
├── config/
│   └── commands.yaml     # Whitelisted commands
├── tests/
│   └── test_basic.py     # Unit tests
├── .env.example          # Environment template
├── .gitignore
├── requirements.txt
├── run.py                # Startup script
└── README.md
```

## 🛠️ Development

### Project Phases

- [x] **Phase 1:** Foundation - Basic Gradio chat with Claude
- [x] **Phase 2:** MCP Server - Define tools with MCP
- [x] **Phase 3:** SSH Connection - Remote command execution
- [ ] **Phase 4:** Tool Definitions - Whitelisted commands
- [ ] **Phase 5:** MCP Client - Agent talks MCP
- [ ] **Phase 6:** Full Integration - End-to-end flow
- [ ] **Phase 7:** Configuration - User-friendly setup
- [ ] **Phase 8:** Security - Hardening and audit
- [ ] **Phase 9:** Polish - Documentation and UX

### Adding New Features

1. Define new commands in `config/commands.yaml`
2. Add corresponding tools in `src/mcp_server.py`
3. Update tool definitions in `src/chat_ui.py`
4. Add tests in `tests/`

## 📄 License

MIT

## 🙏 Acknowledgments

- [Anthropic](https://anthropic.com) for Claude
- [Tailscale](https://tailscale.com) for secure networking
- [Model Context Protocol](https://modelcontextprotocol.io) for the tool framework
- [Gradio](https://gradio.app) for the UI
