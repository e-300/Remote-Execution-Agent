"""
Phase 6: Complete Agentic Chat UI with MCP Integration

This module provides the full chat interface with tool execution capabilities.
Claude can now execute commands on the remote server via MCP tools.

Usage:
    python -m src.chat_ui

Or:
    python src/chat_ui.py
"""

import asyncio
import json
from typing import Any, cast

import gradio as gr
from anthropic import Anthropic
from anthropic.types import ToolParam, TextBlock
from dotenv import load_dotenv

from .config import AgentConfig, get_whitelisted_commands, CommandCategory

# Load environment variables
load_dotenv()


def create_claude_client(agent_config: AgentConfig) -> Anthropic:
    """Create and return an Anthropic client."""
    return Anthropic(api_key=agent_config.anthropic_api_key)


def get_ssh_status(agent_config: AgentConfig) -> tuple[bool, str]:
    """Check if SSH is configured and return status."""
    if agent_config.ssh is None:
        return False, "SSH configuration missing (REMOTE_HOST/REMOTE_USER not set)"
    return True, f"SSH configured for {agent_config.ssh.user}@{agent_config.ssh.host}"


def get_mcp_tools() -> list[ToolParam]:
    """Get tool definitions for Claude API."""
    return [
        {
            "name": "ping",
            "description": "Test if the MCP server is responding. Returns 'pong' if healthy.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Optional message to echo back",
                    }
                },
            },
        },
        {
            "name": "server_status",
            "description": "Get the status of the MCP server and SSH connection. Use this first to check connectivity.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "list_commands",
            "description": "List all available whitelisted commands that can be executed on the remote server.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional: filter by category (system, disk, network, process, service, docker)",
                    }
                },
            },
        },
        {
            "name": "execute_command",
            "description": "Execute a whitelisted command on the remote server. Use 'list_commands' first to see available commands.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command_name": {
                        "type": "string",
                        "description": "Name of the command to execute (e.g., 'disk_usage', 'memory_usage', 'uptime')",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Optional parameters for commands that need them",
                    },
                },
                "required": ["command_name"],
            },
        },
        {
            "name": "check_disk",
            "description": "Check disk space usage on the remote server. Shows all mounted filesystems.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "check_memory",
            "description": "Check memory (RAM) usage on the remote server.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "check_service",
            "description": "Check the status of a systemd service on the remote server.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service (e.g., 'nginx', 'docker', 'ssh')",
                    }
                },
                "required": ["service_name"],
            },
        },
        {
            "name": "check_path_size",
            "description": "Check disk usage for a specific directory or file path.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to check (e.g., '/var/log', '/home')",
                    }
                },
                "required": ["path"],
            },
        },
        {
            "name": "system_overview",
            "description": "Get a comprehensive overview of the remote system including hostname, uptime, memory, and disk usage.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


async def execute_tool(name: str, arguments: dict[str, Any], agent_config: AgentConfig) -> str:
    """
    Execute an MCP tool and return the result.
    
    This function handles the actual execution of tools by calling
    the appropriate SSH commands on the remote server.
    """
    from .ssh_client import SSHClient, test_ssh_connection
    
    try:
        # Handle ping (no SSH needed)
        if name == "ping":
            return json.dumps({
                "status": "pong",
                "message": arguments.get("message", "ping"),
                "server": "remote_exec_mcp",
            }, indent=2)
        
        # Handle list_commands (no SSH needed)
        if name == "list_commands":
            commands = get_whitelisted_commands()
            category = arguments.get("category")
            if category:
                try:
                    cat = CommandCategory(category.lower())
                    commands = [c for c in commands if c.category == cat]
                except ValueError:
                    return json.dumps({
                        "error": f"Unknown category '{category}'",
                        "valid_categories": ["system", "disk", "network", "process", "service", "docker"],
                    }, indent=2)
            
            result: list[dict[str, Any]] = []
            for cmd in commands:
                cmd_info: dict[str, Any] = {
                    "name": cmd.name,
                    "description": cmd.description,
                    "category": cmd.category.value,
                }
                if cmd.parameters:
                    cmd_info["parameters"] = cmd.parameters
                result.append(cmd_info)
            
            return json.dumps({"count": len(result), "commands": result}, indent=2)
        
        # All other tools need SSH
        if agent_config.ssh is None:
            return json.dumps({
                "success": False,
                "error": "SSH not configured: set REMOTE_HOST and REMOTE_USER",
                "hint": "Set REMOTE_HOST, REMOTE_USER, and REMOTE_SSH_KEY_PATH in .env",
            }, indent=2)

        config = agent_config.ssh
        
        # Handle server_status
        if name == "server_status":
            success, msg = await test_ssh_connection(config)
            return json.dumps({
                "server_name": "remote_exec_mcp",
                "version": "0.1.0",
                "ssh": {
                    "status": "connected" if success else "disconnected",
                    "message": msg,
                    "host": f"{config.user}@{config.host}",
                },
            }, indent=2)
        
        # Execute SSH commands
        async with SSHClient(config) as client:
            if name == "check_disk":
                cmd_result = await client.run_whitelisted_command("disk_usage")
            elif name == "check_memory":
                cmd_result = await client.run_whitelisted_command("memory_usage")
            elif name == "check_service":
                service = arguments.get("service_name", "")
                if not service:
                    return json.dumps({"success": False, "error": "service_name is required"}, indent=2)
                cmd_result = await client.run_whitelisted_command(
                    "service_status",
                    {"service_name": service}
                )
            elif name == "check_path_size":
                path = arguments.get("path", "")
                if not path:
                    return json.dumps({"success": False, "error": "path is required"}, indent=2)
                cmd_result = await client.run_whitelisted_command(
                    "disk_usage_path",
                    {"path": path}
                )
            elif name == "system_overview":
                results: dict[str, str] = {}
                for cmd in ["hostname", "uptime", "memory_usage", "disk_usage"]:
                    r = await client.run_whitelisted_command(cmd)
                    results[cmd] = r.stdout.strip() if r.success else f"Error: {r.error_message}"
                return json.dumps({"success": True, "system": results}, indent=2)
            elif name == "execute_command":
                cmd_name = arguments.get("command_name", "")
                if not cmd_name:
                    return json.dumps({"success": False, "error": "command_name is required"}, indent=2)
                cmd_result = await client.run_whitelisted_command(
                    cmd_name,
                    arguments.get("parameters")
                )
            else:
                return json.dumps({"success": False, "error": f"Unknown tool: {name}"}, indent=2)
            
            # Format result
            if cmd_result.success:
                return json.dumps({
                    "success": True,
                    "command": cmd_result.command,
                    "output": cmd_result.stdout.strip() if cmd_result.stdout else "(no output)",
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "command": cmd_result.command,
                    "error": cmd_result.error_message or cmd_result.stderr,
                    "exit_code": cmd_result.exit_code,
                }, indent=2)
                
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "tool": name,
        }, indent=2)


def get_system_prompt(agent_config: AgentConfig) -> str:
    """Generate system prompt with context about available tools."""
    ssh_ok, ssh_status = get_ssh_status(agent_config)
    
    return f"""You are a helpful assistant that can execute commands on a remote server via SSH and Tailscale.

**Connection Status:** {"✅ " + ssh_status if ssh_ok else "⚠️ " + ssh_status}

**Available Tools:**
- `ping` - Test if the server is responding
- `server_status` - Check SSH connection status
- `list_commands` - See all available commands
- `execute_command` - Run a specific whitelisted command
- `check_disk` - Quick disk space check
- `check_memory` - Quick memory usage check  
- `check_service` - Check a systemd service status
- `check_path_size` - Check size of a directory
- `system_overview` - Get comprehensive system info

**How to help users:**
1. When asked about the server, USE THE TOOLS to get real data - don't just describe what you could do
2. Start with `server_status` if unsure about connectivity
3. Use `system_overview` for a quick health check
4. Be concise in responses, but include relevant details from tool output
5. If a command fails, explain what happened and suggest alternatives

**Security:**
- Only whitelisted commands can be executed
- All communication happens over Tailscale's encrypted network
- Parameters are sanitized to prevent injection"""


async def chat_with_tools(
    message: str,
    history: list[dict[str, str]],
    client: Anthropic,
    agent_config: AgentConfig,
) -> str:
    """
    Send a message to Claude with tool use capability.
    
    Implements the agentic loop where Claude can call tools
    multiple times before generating a final response.
    """
    # Build messages from history
    messages: list[dict[str, Any]] = []
    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })
    
    # Add current message
    messages.append({
        "role": "user",
        "content": message,
    })
    
    tools = get_mcp_tools()
    max_iterations = 10
    
    for _ in range(max_iterations):
        # Call Claude
        response = client.messages.create(
            model=agent_config.model,
            max_tokens=agent_config.max_tokens,
            system=get_system_prompt(agent_config),
            tools=tools,
            messages=messages,  # type: ignore[arg-type]
        )
        
        # Check if Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Add assistant's response (with tool use blocks)
            messages.append({
                "role": "assistant",
                "content": response.content,  # type: ignore[dict-item]
            })
            
            # Process each tool use
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    # Execute the tool
                    result = await execute_tool(block.name, cast(dict[str, Any], block.input), agent_config)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            
            # Add tool results
            messages.append({
                "role": "user",
                "content": tool_results,  # type: ignore[dict-item]
            })
        else:
            # Claude is done - extract final text response
            final_text = ""
            for block in response.content:
                if isinstance(block, TextBlock):
                    final_text += block.text
            return final_text
    
    return "I've reached the maximum number of tool calls. Please try a simpler request."


def create_chat_interface(agent_config: AgentConfig) -> gr.Blocks:
    """Create and return the Gradio chat interface with tool support."""
    
    # Initialize Claude client
    try:
        client = create_claude_client(agent_config)
        claude_status = "✅ Connected to Claude API"
    except ValueError as e:
        client = None
        claude_status = f"❌ {e}"
    
    # Check SSH status
    ssh_ok, ssh_status = get_ssh_status(agent_config)
    ssh_display = f"✅ {ssh_status}" if ssh_ok else f"⚠️ {ssh_status}"
    
    with gr.Blocks(
        title="Tailscale MCP Agent",
    ) as demo:
        gr.Markdown(
            """
            # 🔐 Tailscale MCP Agent
            
            Chat with Claude to execute commands on your remote server via SSH and Tailscale.
            """
        )
        
        # Status indicators
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown(f"**Claude API:** {claude_status}")
            with gr.Column(scale=1):
                gr.Markdown(f"**SSH:** {ssh_display}")
        
        if client is None:
            gr.Markdown(
                """
                ### ⚠️ Setup Required
                
                1. Copy `.env.example` to `.env`
                2. Add your `ANTHROPIC_API_KEY`
                3. Add your SSH configuration:
                   - `REMOTE_HOST` (Tailscale IP)
                   - `REMOTE_USER`
                   - `REMOTE_SSH_KEY_PATH`
                4. Restart the application
                """
            )
            return demo
        
        # Chat interface
        chatbot: gr.Chatbot = gr.Chatbot(
            label="Conversation",
            height=500,
        )
        
        msg = gr.Textbox(
            label="Your message",
            placeholder="Try: 'Check the disk space on the server' or 'What's the system status?'",
            lines=2,
            max_lines=10,
        )
        
        with gr.Row():
            submit_btn = gr.Button("Send", variant="primary")
            clear_btn = gr.Button("Clear")
        
        # Example prompts
        gr.Examples(
            examples=[
                "Check the server status",
                "How much disk space is available?",
                "Show me the memory usage",
                "Give me a system overview",
                "What commands can you run?",
                "Is the docker service running?",
                "Check the size of /var/log",
            ],
            inputs=msg,
            label="Example prompts",
        )
        
        # Info accordion
        with gr.Accordion("Available Commands", open=False):
            gr.Markdown(
                """
                **System:** hostname, uptime, whoami, uname
                
                **Disk:** disk_usage, disk_usage_path
                
                **Memory:** memory_usage
                
                **Process:** top_processes, process_count
                
                **Network:** network_interfaces, listening_ports
                
                **Services:** service_status, failed_services
                
                **Docker:** docker_ps, docker_stats
                """
            )
        
        def respond(
            message: str,
            history: list[dict[str, str]],
        ) -> tuple[str, list[dict[str, str]]]:
            """Handle user message with tool execution."""
            if not message.strip():
                return "", history
            
            # History is already in dict format for Gradio 6.0
            history_dicts: list[dict[str, str]] = list(history) if history else []
            
            # Get response with tools (run async)
            response = asyncio.run(chat_with_tools(message, history_dicts, client, agent_config))
            
            # Add to history in Gradio 6.0 message format
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ]
            
            return "", history
        
        # Wire up events
        msg.submit(
            respond,
            inputs=[msg, chatbot],
            outputs=[msg, chatbot],
        )
        
        submit_btn.click(
            respond,
            inputs=[msg, chatbot],
            outputs=[msg, chatbot],
        )
        
        clear_btn.click(
            lambda: ("", []),
            inputs=None,
            outputs=[msg, chatbot],
        )
    
    return demo


def main(agent_config: AgentConfig | None = None) -> None:
    """Launch the chat interface."""
    if agent_config is None:
        agent_config = AgentConfig.from_env()
    print("🚀 Starting Tailscale MCP Agent...")
    print("   Phase 6: Full Agentic Loop with Tool Execution")
    print()
    
    # Check configuration
    ssh_ok, ssh_msg = get_ssh_status(agent_config)
    if ssh_ok:
        print(f"   ✅ SSH: {ssh_msg}")
    else:
        print(f"   ⚠️  SSH: {ssh_msg}")
    
    try:
        create_claude_client(agent_config)
        print("   ✅ Claude API: Connected")
    except ValueError as e:
        print(f"   ❌ Claude API: {e}")
    
    print()
    print(f"   Open http://localhost:{agent_config.ui_port} in your browser")
    print()
    
    demo = create_chat_interface(agent_config)
    demo.launch(
        server_name="0.0.0.0",
        server_port=agent_config.ui_port,
        share=False,
    )


if __name__ == "__main__":
    main()