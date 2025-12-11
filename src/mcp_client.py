"""
Phase 5: MCP Client Integration

This module provides the MCP client that the agent uses to communicate
with the MCP server. It handles tool discovery and execution.

For this project, we use an in-process client that calls tools directly
rather than going through stdio transport, which simplifies deployment.
"""

import asyncio
import json
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class MCPTool:
    """Representation of an MCP tool for use with Claude."""
    
    name: str
    description: str
    input_schema: dict[str, Any]
    
    def to_claude_format(self) -> dict[str, Any]:
        """Convert to Claude API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class ToolResult:
    """Result from executing an MCP tool."""
    
    tool_name: str
    success: bool
    content: str
    error: Optional[str] = None


class InProcessMCPClient:
    """
    In-process MCP client that calls tools directly.
    
    This client runs the MCP tools in the same process rather than
    using stdio transport. This simplifies deployment and avoids
    the complexity of subprocess management.
    """
    
    def __init__(self) -> None:
        """Initialize in-process client."""
        self._tools: dict[str, MCPTool] = {}
        self._connected = False
    
    async def connect(self) -> None:
        """
        Initialize and discover tools from the MCP server module.
        """
        # Define available tools manually (matching mcp_server.py)
        self._tools = {
            "ping": MCPTool(
                name="ping",
                description="Test if the MCP server is responding",
                input_schema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Optional message to echo back",
                        }
                    },
                },
            ),
            "server_status": MCPTool(
                name="server_status",
                description="Get the status of the MCP server and SSH connection",
                input_schema={"type": "object", "properties": {}},
            ),
            "list_commands": MCPTool(
                name="list_commands",
                description="List all available whitelisted commands",
                input_schema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category",
                        }
                    },
                },
            ),
            "execute_command": MCPTool(
                name="execute_command",
                description="Execute a whitelisted command on the remote server",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command_name": {
                            "type": "string",
                            "description": "Name of the command to execute",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Optional parameters",
                        },
                    },
                    "required": ["command_name"],
                },
            ),
            "check_disk": MCPTool(
                name="check_disk",
                description="Check disk space usage on the remote server",
                input_schema={"type": "object", "properties": {}},
            ),
            "check_memory": MCPTool(
                name="check_memory",
                description="Check memory usage on the remote server",
                input_schema={"type": "object", "properties": {}},
            ),
            "check_service": MCPTool(
                name="check_service",
                description="Check the status of a systemd service",
                input_schema={
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Name of the service to check",
                        }
                    },
                    "required": ["service_name"],
                },
            ),
            "check_path_size": MCPTool(
                name="check_path_size",
                description="Check disk usage for a specific path",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to check",
                        }
                    },
                    "required": ["path"],
                },
            ),
            "system_overview": MCPTool(
                name="system_overview",
                description="Get a comprehensive system overview",
                input_schema={"type": "object", "properties": {}},
            ),
        }
        
        self._connected = True
    
    async def disconnect(self) -> None:
        """Disconnect (no-op for in-process)."""
        self._connected = False
        self._tools = {}
    


    async def __aenter__(self) -> "InProcessMCPClient":
        await self.connect()
        return self
    


    async def __aexit__(
        self, 
        exc_type: Any, 
        exc_val: Any, 
        exc_tb: Any
    ) -> None:
        await self.disconnect()
    


    def get_tools(self) -> list[MCPTool]:
        """Get all available tools."""
        return list(self._tools.values())
    



    def get_tools_for_claude(self) -> list[dict[str, Any]]:
        """Get tools formatted for Claude API."""
        return [tool.to_claude_format() for tool in self._tools.values()]
    


    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool by calling it directly."""
        if not self._connected:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                content="",
                error="Client not connected",
            )
        
        # Import and execute tools directly
        from .config import SSHConfig, get_whitelisted_commands, CommandCategory
        from .ssh_client import SSHClient, test_ssh_connection
        
        try:
            # Handle ping (no SSH needed)
            if tool_name == "ping":
                result = json.dumps({
                    "status": "pong",
                    "message": arguments.get("message", "ping"),
                    "server": "remote_exec_mcp",
                }, indent=2)
                return ToolResult(tool_name=tool_name, success=True, content=result)
            
            # Handle list_commands (no SSH needed)
            if tool_name == "list_commands":
                commands = get_whitelisted_commands()
                category = arguments.get("category")
                if category:
                    try:
                        cat = CommandCategory(category.lower())
                        commands = [c for c in commands if c.category == cat]
                    except ValueError:
                        return ToolResult(
                            tool_name=tool_name,
                            success=True,
                            content=json.dumps({
                                "error": f"Unknown category '{category}'",
                                "valid_categories": [c.value for c in CommandCategory],
                            }, indent=2),
                        )
                
                cmd_list: list[dict[str, Any]] = []
                for cmd in commands:
                    cmd_info: dict[str, Any] = {
                        "name": cmd.name,
                        "description": cmd.description,
                        "category": cmd.category.value,
                    }
                    if cmd.parameters:
                        cmd_info["parameters"] = cmd.parameters
                    cmd_list.append(cmd_info)
                
                return ToolResult(
                    tool_name=tool_name,
                    success=True,
                    content=json.dumps({"count": len(cmd_list), "commands": cmd_list}, indent=2),
                )
            
            # All other tools need SSH
            try:
                config = SSHConfig.from_env()
            except ValueError as e:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    content="",
                    error=f"SSH not configured: {e}",
                )
            
            # Handle server_status
            if tool_name == "server_status":
                success, msg = await test_ssh_connection(config)
                result = json.dumps({
                    "server_name": "remote_exec_mcp",
                    "version": "0.1.0",
                    "ssh": {
                        "status": "connected" if success else "disconnected",
                        "message": msg,
                    },
                }, indent=2)
                return ToolResult(tool_name=tool_name, success=True, content=result)
            
            # Execute SSH commands
            async with SSHClient(config) as client:
                if tool_name == "check_disk":
                    cmd_result = await client.run_whitelisted_command("disk_usage")
                elif tool_name == "check_memory":
                    cmd_result = await client.run_whitelisted_command("memory_usage")
                elif tool_name == "check_service":
                    service = arguments.get("service_name", "")
                    if not service:
                        return ToolResult(
                            tool_name=tool_name,
                            success=False,
                            content="",
                            error="service_name is required",
                        )
                    cmd_result = await client.run_whitelisted_command(
                        "service_status", 
                        {"service_name": service}
                    )
                elif tool_name == "check_path_size":
                    path = arguments.get("path", "")
                    if not path:
                        return ToolResult(
                            tool_name=tool_name,
                            success=False,
                            content="",
                            error="path is required",
                        )
                    cmd_result = await client.run_whitelisted_command(
                        "disk_usage_path",
                        {"path": path}
                    )
                elif tool_name == "system_overview":
                    results: dict[str, str] = {}
                    for cmd in ["hostname", "uptime", "memory_usage", "disk_usage"]:
                        r = await client.run_whitelisted_command(cmd)
                        results[cmd] = r.stdout.strip() if r.success else f"Error: {r.error_message}"
                    return ToolResult(
                        tool_name=tool_name,
                        success=True,
                        content=json.dumps({"success": True, "system": results}, indent=2),
                    )
                elif tool_name == "execute_command":
                    cmd_name = arguments.get("command_name", "")
                    if not cmd_name:
                        return ToolResult(
                            tool_name=tool_name,
                            success=False,
                            content="",
                            error="command_name is required",
                        )
                    cmd_result = await client.run_whitelisted_command(
                        cmd_name,
                        arguments.get("parameters"),
                    )
                else:
                    return ToolResult(
                        tool_name=tool_name,
                        success=False,
                        content="",
                        error=f"Unknown tool: {tool_name}",
                    )
                
                # Format result
                if cmd_result.success:
                    content = json.dumps({
                        "success": True,
                        "command": cmd_result.command,
                        "output": cmd_result.stdout.strip(),
                    }, indent=2)
                else:
                content = json.dumps({
                    "success": False,
                    "error": cmd_result.error_message or cmd_result.stderr,
                }, indent=2)

                return ToolResult(tool_name=tool_name, success=cmd_result.success, content=content)
                
        except Exception as e:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                content="",
                error=str(e),
            )


# =============================================================================
# CLI Testing
# =============================================================================

async def _test_main() -> None:
    """Test MCP client functionality."""
    print("MCP Client Test")
    print("=" * 50)
    
    # Use in-process client for testing
    async with InProcessMCPClient() as client:
        # List tools
        print("\nAvailable tools:")
        for tool in client.get_tools():
            desc = tool.description[:50] + "..." if len(tool.description) > 50 else tool.description
            print(f"  - {tool.name}: {desc}")
        
        # Test ping
        print("\nTesting ping...")
        result = await client.execute_tool("ping", {"message": "hello"})
        print(f"  Success: {result.success}")
        print(f"  Content: {result.content}")
        
        # Test list_commands
        print("\nTesting list_commands...")
        result = await client.execute_tool("list_commands", {})
        print(f"  Success: {result.success}")
        if result.success:
            data = json.loads(result.content)
            print(f"  Found {data['count']} commands")


if __name__ == "__main__":
    asyncio.run(_test_main())