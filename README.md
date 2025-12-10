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

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 Tailnet                                     │
│                                                                             │
│  ┌──────────────┐         ┌─────────────────────┐         ┌──────────────┐  │
│  │    Local     │ ◄──────►│       Agent         │ ◄──────►│Remote Server │  │
│  │   Browser    │   HTTP  │   (self-hosted)     │   SSH   │              │  │
│  └──────────────┘         │                     │         │ Executes:    │  │
│                           │  - Gradio UI        │         │  df -h       │  │
│                           │  - MCP tools        │         │  free -m     │  │
│                           │  - SSH client       │         │  systemctl   │  │
│                           └──────────┬──────────┘         └──────────────┘  │
│                                      │                                      │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
                                       │ HTTPS (API call)
                                       ▼
                               ┌──────────────────┐
                               │  Anthropic API   │
                               └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Tailscale** installed and connected on both machines, both should be in your tailnet
- **SSH access** to your remote server (key-based auth recommended)
- **Anthropic API key** ([get one here](https://console.anthropic.com/))

### Setup

1. **Clone and setup environment:**
   ```bash
   git clone <this-repo>
   cd tailscale-mcp-agent
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   
   Blank .env file is provided for you
   Just fill in your info
   Edit `.env` with your values:
   ```env
   ANTHROPIC_API_KEY=sk-your-key
   REMOTE_HOST=100.x.x.x          # Your Tailscale IP
   REMOTE_USER=server-username
   REMOTE_SSH_KEY_PATH=~/.ssh/id_ed25519
   REMOTE_SSH_KEY_PASSPHRASE=if-needed-else-leave-blank
   REMOTE_SSH_PORT=if-needed-else-leave-blank

   ```

3. **Run the agent:**
   ```bash
   python run.py
   ```

4. **Open in browser:**
   Navigate to `http://localhost:7860`

## 📖 Usage

### Example Commands

Once running, try these prompts:

- **"Check the server status"** - Verifies SSH connectivity
- **"How much disk space is available?"** - Runs `df -h`
- **"Show me the memory usage"** - Runs `free -h`
- **"Give me a system overview"** - Runs multiple commands
- **"What commands can you run?"** - Lists all whitelisted commands
- **"Is the docker service running?"** - Checks systemd service
- **"Check the size of /var/log"** - Runs `du -sh /var/log`

### Available Tools

| Tool | Description |
|------|-------------|
| `ping` | Test MCP server connectivity |
| `server_status` | Check SSH connection status |
| `list_commands` | Show all available commands |
| `execute_command` | Run a whitelisted command |
| `check_disk` | Quick disk space check |
| `check_memory` | Quick memory check |
| `check_service` | Check a systemd service |
| `check_path_size` | Check directory size |
| `system_overview` | Get comprehensive system info |

### Whitelisted Commands

Commands are organized by category:

- **System:** hostname, uptime, whoami, uname, date
- **Disk:** disk_usage, disk_usage_path, largest_files
- **Memory:** memory_usage, memory_detailed
- **Process:** top_processes, top_memory_processes, process_count
- **Network:** network_interfaces, listening_ports, routing_table
- **Services:** service_status, failed_services, service_logs
- **Docker:** docker_ps, docker_stats, docker_logs, docker_images

See `config/commands.yaml` for the full list and to add custom commands.

## 🔒 Security

### Design Principles

1. **Command Whitelisting** - Only pre-approved commands can run
2. **Parameter Sanitization** - All inputs are sanitized to prevent injection
3. **Tailscale Encryption** - All traffic between machines is encrypted
4. **SSH Key Auth** - Password authentication not supported
5. **No Shell Access** - Commands run in isolation, not interactive shells

### Adding Custom Commands

Edit `config/commands.yaml`:

```yaml
- name: my_custom_command
  description: What this command does (be descriptive for Claude)
  command_template: echo "Hello {name}"
  category: custom
  parameters:
    name: The name to greet
```

### Security Audit Checklist

Before deploying:
- [ ] Review all commands in `config/commands.yaml`
- [ ] Remove any commands you don't need
- [ ] Verify SSH key has minimal permissions on remote server
- [ ] Consider running the agent in a container
- [ ] Enable Tailscale ACLs to restrict access
- [ ] Run check_setup.py to verify dependencies are installed correctly

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

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src

# Test SSH connection manually
python -c "
import asyncio
from src.config import SSHConfig
from src.ssh_client import test_ssh_connection

config = SSHConfig.from_env()
result = asyncio.run(test_ssh_connection(config))
print(result)
"
```

## 🔧 Troubleshooting

### "SSH not configured"
Make sure all these are set in `.env`:
- `REMOTE_HOST`
- `REMOTE_USER`
- `REMOTE_SSH_KEY_PATH`

### "SSH key not found"
Check that your key path is correct and the file exists:
```bash
ls -la ~/.ssh/id_ed25519
```

### "Connection refused"
1. Verify Tailscale is running: `tailscale status`
2. Check you can ping the remote: `ping 100.x.x.x`
3. Verify SSH is running on remote: `ssh user@100.x.x.x`

### "Command not in whitelist"
Add the command to `config/commands.yaml` or use `list_commands` to see available options.

## 🛠️ Development

### Project Phases

- [x] **Phase 1:** Foundation - Basic Gradio chat with Claude
- [x] **Phase 2:** MCP Server - Define tools with MCP
- [x] **Phase 3:** SSH Connection - Remote command execution
- [x] **Phase 4:** Tool Definitions - Whitelisted commands
- [x] **Phase 5:** MCP Client - Agent talks MCP
- [x] **Phase 6:** Full Integration - End-to-end flow
- [x] **Phase 7:** Configuration - User-friendly setup
- [x] **Phase 8:** Security - Hardening and audit
- [x] **Phase 9:** Polish - Documentation and UX

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