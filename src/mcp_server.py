"""
Phase 4: MCP Server with Real SSH Tools

This module implements the MCP server that exposes tools for remote command execution.
Tools are connected to the SSH client for real command execution on remote servers.

Usage:
    # Run standalone for testing
    python -m src.mcp_server
    
    # Or test with MCP inspector
    npx @modelcontextprotocol/inspector python -m src.mcp_server
"""

import json
from typing import Optional, Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

from .config import (
    SSHConfig, 
    DEFAULT_COMMANDS, 
    get_command_by_name,
    CommandCategory,
)
from .ssh_client import SSHClient, test_ssh_connection, CommandResult


# Initialize MCP server
mcp = FastMCP("remote_exec_mcp")

# Global state for SSH config (loaded on first use)
_ssh_config: Optional[SSHConfig] = None


def _get_ssh_config() -> SSHConfig:
    """Get or load SSH config from environment."""
    global _ssh_config
    if _ssh_config is None:
        _ssh_config = SSHConfig.from_env()
    return _ssh_config


# =============================================================================
# Input Models (Pydantic)
# =============================================================================

class PingInput(BaseModel):
    """Input for the ping tool - used to test if server is responding."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )
    
    message: Optional[str] = Field(
        default="ping",
        description="Optional message to echo back (default: 'ping')",
        max_length=100,
    )


class ServerStatusInput(BaseModel):
    """Input for server status tool - no parameters needed."""
    model_config = ConfigDict(extra="forbid")


class ListCommandsInput(BaseModel):
    """Input for listing available commands."""
    
    model_config = ConfigDict(extra="forbid")
    
    category: Optional[str] = Field(
        default=None,
        description="Filter by category: system, disk, network, process, service, docker, custom",
    )


class ExecuteCommandInput(BaseModel):
    """Input for executing a whitelisted command."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )
    
    command_name: str = Field(
        ...,
        description="Name of the whitelisted command to execute (e.g., 'disk_usage', 'memory_usage')",
        min_length=1,
        max_length=50,
    )
    
    parameters: Optional[dict[str, str]] = Field(
        default=None,
        description="Optional parameters for commands that need them (e.g., {'path': '/var/log'})",
    )


class ServiceStatusInput(BaseModel):
    """Input for checking a specific service status."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )
    
    service_name: str = Field(
        ...,
        description="Name of the systemd service to check (e.g., 'nginx', 'docker', 'ssh')",
        pattern=r"^[a-zA-Z0-9_-]+$",
        min_length=1,
        max_length=50,
    )


class DiskUsagePathInput(BaseModel):
    """Input for checking disk usage of a specific path."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )
    
    path: str = Field(
        ...,
        description="Path to check disk usage for (e.g., '/var/log', '/home')",
        pattern=r"^[a-zA-Z0-9._/-]+$",
        min_length=1,
        max_length=200,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def format_command_result(result: CommandResult) -> str:
    """Format a command result for display."""
    if result.success:
        output = result.stdout.strip() if result.stdout else "(no output)"
        return json.dumps({
            "success": True,
            "command": result.command,
            "output": output,
        }, indent=2)
    else:
        return json.dumps({
            "success": False,
            "command": result.command,
            "error": result.error_message or result.stderr,
            "exit_code": result.exit_code,
        }, indent=2)


# =============================================================================
# MCP Tool Definitions
# =============================================================================

@mcp.tool(name="ping")
async def ping(params: PingInput) -> str:
    """
    Test if the MCP server is responding.
    
    This is a simple connectivity check that returns 'pong' along with
    any message you send. Use this to verify the MCP server is running
    before attempting remote commands.
    
    Args:
        params: PingInput containing optional message
        
    Returns:
        JSON response with status and echoed message
    """
    return json.dumps({
        "status": "pong",
        "message": params.message,
        "server": "remote_exec_mcp",
    }, indent=2)


@mcp.tool(name="server_status")
async def server_status(params: ServerStatusInput) -> str:
    """
    Get the status of the MCP server and SSH connection.
    
    Returns information about the server including SSH connection status
    and available commands. Use this first to verify connectivity before
    executing remote commands.
    
    Args:
        params: Empty input (no parameters needed)
        
    Returns:
        JSON with server status information
    """
    try:
        config = _get_ssh_config()
        ssh_host = f"{config.user}@{config.host}"
        success, msg = await test_ssh_connection(config)
        ssh_status = "connected" if success else f"error: {msg}"
    except ValueError as e:
        ssh_status = f"not_configured: {e}"
        ssh_host = None
    except Exception as e:
        ssh_status = f"error: {e}"
        ssh_host = None
    
    status: dict[str, Any] = {
        "server_name": "remote_exec_mcp",
        "version": "0.1.0",
        "status": "healthy",
        "ssh": {
            "status": ssh_status,
            "host": ssh_host,
        },
        "available_command_count": len(DEFAULT_COMMANDS),
        "categories": [cat.value for cat in CommandCategory],
    }
    return json.dumps(status, indent=2)


@mcp.tool(name="list_commands")
async def list_commands(params: ListCommandsInput) -> str:
    """
    List all available whitelisted commands that can be executed.
    
    Use this to discover what commands are available before trying to
    execute them. Commands are organized by category (system, disk,
    network, process, service, docker).
    
    Args:
        params: Optional category filter
        
    Returns:
        JSON list of available commands with descriptions
    """
    commands = list(DEFAULT_COMMANDS)
    
    # Filter by category if specified
    if params.category:
        try:
            cat = CommandCategory(params.category.lower())
            commands = [c for c in commands if c.category == cat]
        except ValueError:
            return json.dumps({
                "error": f"Unknown category '{params.category}'",
                "valid_categories": [c.value for c in CommandCategory],
            }, indent=2)
    
    # Format command list
    result: list[dict[str, Any]] = []
    for cmd in commands:
        cmd_info: dict[str, Any] = {
            "name": cmd.name,
            "description": cmd.description,
            "category": cmd.category.value,
        }
        if cmd.parameters:
            cmd_info["parameters"] = cmd.parameters
        if cmd.example_usage:
            cmd_info["example"] = cmd.example_usage
        result.append(cmd_info)
    
    return json.dumps({
        "count": len(result),
        "commands": result,
    }, indent=2)


@mcp.tool(name="execute_command")
async def execute_command(params: ExecuteCommandInput) -> str:
    """
    Execute a whitelisted command on the remote server.
    
    Only pre-approved commands from the whitelist can be executed.
    Use 'list_commands' first to see available commands and their parameters.
    
    Args:
        params: Command name and optional parameters
        
    Returns:
        JSON with command output or error message
    """
    # Validate command exists
    cmd_def = get_command_by_name(params.command_name)
    if cmd_def is None:
        available = [c.name for c in DEFAULT_COMMANDS]
        return json.dumps({
            "success": False,
            "error": f"Unknown command '{params.command_name}'",
            "hint": "Use 'list_commands' to see available commands",
            "available_commands": available[:10],
        }, indent=2)
    
    # Get SSH config
    try:
        config = _get_ssh_config()
    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "hint": "Configure SSH connection in environment variables",
        }, indent=2)
    
    # Execute command
    try:
        async with SSHClient(config) as client:
            result = await client.run_whitelisted_command(
                params.command_name,
                params.parameters,
            )
            return format_command_result(result)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
        }, indent=2)


# =============================================================================
# Convenience Tools (shortcuts for common operations)
# =============================================================================

@mcp.tool(name="check_disk")
async def check_disk() -> str:
    """
    Check disk space usage on the remote server.
    
    Shows disk usage for all mounted filesystems in human-readable format.
    Equivalent to running 'df -h'.
    
    Returns:
        Disk usage information
    """
    try:
        config = _get_ssh_config()
        async with SSHClient(config) as client:
            result = await client.run_whitelisted_command("disk_usage")
            return format_command_result(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool(name="check_memory")
async def check_memory() -> str:
    """
    Check memory usage on the remote server.
    
    Shows RAM and swap usage in human-readable format.
    Equivalent to running 'free -h'.
    
    Returns:
        Memory usage information
    """
    try:
        config = _get_ssh_config()
        async with SSHClient(config) as client:
            result = await client.run_whitelisted_command("memory_usage")
            return format_command_result(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool(name="check_service")
async def check_service(params: ServiceStatusInput) -> str:
    """
    Check the status of a systemd service on the remote server.
    
    Use this to verify if services like nginx, docker, ssh, etc. are running.
    
    Args:
        params: Service name to check
        
    Returns:
        Service status information
    """
    try:
        config = _get_ssh_config()
        async with SSHClient(config) as client:
            result = await client.run_whitelisted_command(
                "service_status",
                {"service_name": params.service_name},
            )
            return format_command_result(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool(name="check_path_size")
async def check_path_size(params: DiskUsagePathInput) -> str:
    """
    Check disk usage for a specific path on the remote server.
    
    Shows the total size of a directory or file.
    
    Args:
        params: Path to check
        
    Returns:
        Size of the specified path
    """
    try:
        config = _get_ssh_config()
        async with SSHClient(config) as client:
            result = await client.run_whitelisted_command(
                "disk_usage_path",
                {"path": params.path},
            )
            return format_command_result(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool(name="system_overview")
async def system_overview() -> str:
    """
    Get a comprehensive overview of the remote system.
    
    Runs multiple commands to gather hostname, uptime, memory, and disk info
    in a single call. Use this for a quick health check.
    
    Returns:
        JSON with system overview including hostname, uptime, memory, and disk
    """
    try:
        config = _get_ssh_config()
        async with SSHClient(config) as client:
            # Run multiple commands
            commands = ["hostname", "uptime", "memory_usage", "disk_usage"]
            results: dict[str, str] = {}
            
            for cmd_name in commands:
                result = await client.run_whitelisted_command(cmd_name)
                if result.success:
                    results[cmd_name] = result.stdout.strip()
                else:
                    results[cmd_name] = f"Error: {result.error_message}"
            
            return json.dumps({
                "success": True,
                "system": results,
            }, indent=2)
            
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> None:
    """Run the MCP server."""
    print("🚀 Starting Remote Exec MCP Server...")
    print("   Use Ctrl+C to stop")
    print()
    print("   Test with MCP Inspector:")
    print("   npx @modelcontextprotocol/inspector python -m src.mcp_server")
    print()
    
    # Run with stdio transport (default for local tools)
    mcp.run()


if __name__ == "__main__":
    main()