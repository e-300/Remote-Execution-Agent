"""
Phase 3: SSH Client Module

This module handles SSH connections and command execution on remote servers.
Uses asyncssh for async SSH operations.

Usage:
    from src.ssh_client import SSHClient
    
    async with SSHClient.from_config(ssh_config) as client:
        result = await client.run_command("whoami")
        print(result.stdout)
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import asyncssh

from .config import SSHConfig, WhitelistedCommand, get_command_by_name


@dataclass
class CommandResult:
    """Result of a remote command execution."""
    
    command: str
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "success": self.success,
            "error_message": self.error_message,
        }


class SSHClientError(Exception):
    """Custom exception for SSH client errors."""
    pass


class SSHClient:
    """
    Async SSH client for executing commands on remote servers.
    
    This client is designed to work with Tailscale-connected servers
    and implements security measures including command whitelisting.
    """
    
    def __init__(self, config: SSHConfig):
        """
        Initialize SSH client with configuration.
        
        Args:
            config: SSHConfig with connection details
        """
        self.config = config
        self._connection: Optional[asyncssh.SSHClientConnection] = None
    
    @classmethod
    def from_config(cls, config: SSHConfig) -> "SSHClient":
        """Create an SSH client from configuration."""
        return cls(config)
    
    async def connect(self) -> None:
        """
        Establish SSH connection to the remote server.
        
        Raises:
            SSHClientError: If connection fails
        """
        if self._connection is not None:
            return  # Already connected
        
        try:
            # Build connection options
            connect_opts = {
                "host": self.config.host,
                "port": self.config.port,
                "username": self.config.user,
                "connect_timeout": self.config.connection_timeout,
            }
            
            # Add key path if specified
            if self.config.key_path:
                # If passphrase is provided, we need to load the key manually
                if self.config.key_passphrase:
                    connect_opts["client_keys"] = [
                        asyncssh.read_private_key(
                            str(self.config.key_path),
                            passphrase=self.config.key_passphrase
                        )
                    ]
                else:
                    connect_opts["client_keys"] = [str(self.config.key_path)]
            
            # Add known_hosts handling
            if self.config.known_hosts_path:
                connect_opts["known_hosts"] = str(self.config.known_hosts_path)
            else:
                # For Tailscale, we often trust the network
                # In production, you'd want proper host key verification
                connect_opts["known_hosts"] = None
            
            self._connection = await asyncssh.connect(**connect_opts)
            
        except asyncssh.Error as e:
            raise SSHClientError(f"SSH connection failed: {e}") from e
        except OSError as e:
            raise SSHClientError(f"Network error: {e}") from e
    
    async def disconnect(self) -> None:
        """Close the SSH connection."""
        if self._connection is not None:
            self._connection.close()
            await self._connection.wait_closed()
            self._connection = None
    
    async def __aenter__(self) -> "SSHClient":
        """Async context manager entry - connect."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - disconnect."""
        await self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if the client is currently connected."""
        return self._connection is not None
    
    async def run_command(
        self,
        command: str,
        timeout: Optional[float] = None,
    ) -> CommandResult:
        """
        Execute a command on the remote server.
        
        Args:
            command: Command string to execute
            timeout: Optional timeout override (uses config default if not specified)
            
        Returns:
            CommandResult with stdout, stderr, and exit code
            
        Raises:
            SSHClientError: If not connected or command execution fails
        """
        if self._connection is None:
            raise SSHClientError("Not connected. Call connect() first.")
        
        timeout = timeout or self.config.command_timeout
        
        try:
            result = await asyncio.wait_for(
                self._connection.run(command, check=False),
                timeout=timeout,
            )
            
            # Handle stdout/stderr which may be bytes or str
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            if isinstance(stdout, (bytes, bytearray, memoryview)):
                stdout = bytes(stdout).decode("utf-8", errors="replace")
            else:
                stdout = str(stdout)
            if isinstance(stderr, (bytes, bytearray, memoryview)):
                stderr = bytes(stderr).decode("utf-8", errors="replace")
            else:
                stderr = str(stderr)
            
            return CommandResult(
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=result.exit_status or 0,
                success=result.exit_status == 0,
            )
            
        except asyncio.TimeoutError:
            return CommandResult(
                command=command,
                stdout="",
                stderr="",
                exit_code=-1,
                success=False,
                error_message=f"Command timed out after {timeout} seconds",
            )
        except asyncssh.Error as e:
            return CommandResult(
                command=command,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                success=False,
                error_message=f"SSH error: {e}",
            )
    
    async def run_whitelisted_command(
        self,
        command_name: str,
        parameters: Optional[dict[str, str]] = None,
    ) -> CommandResult:
        """
        Execute a whitelisted command by name with optional parameters.
        
        This is the safe way to execute commands - it only allows
        pre-defined commands from the whitelist.
        
        Args:
            command_name: Name of the whitelisted command
            parameters: Optional dict of parameter values for placeholders
            
        Returns:
            CommandResult with execution results
            
        Raises:
            SSHClientError: If command is not whitelisted or parameters are invalid
        """
        # Look up the whitelisted command
        cmd_def = get_command_by_name(command_name)
        if cmd_def is None:
            return CommandResult(
                command=command_name,
                stdout="",
                stderr="",
                exit_code=-1,
                success=False,
                error_message=f"Command '{command_name}' is not in the whitelist. "
                             f"Only approved commands can be executed.",
            )
        
        # Build the actual command from template
        try:
            command = self._build_command(cmd_def, parameters or {})
        except ValueError as e:
            return CommandResult(
                command=command_name,
                stdout="",
                stderr="",
                exit_code=-1,
                success=False,
                error_message=str(e),
            )
        
        # Execute the command
        return await self.run_command(command)
    
    def _build_command(
        self,
        cmd_def: WhitelistedCommand,
        parameters: dict[str, str],
    ) -> str:
        """
        Build the actual command string from template and parameters.
        
        Args:
            cmd_def: WhitelistedCommand definition
            parameters: Dict of parameter values
            
        Returns:
            The built command string
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Find all placeholders in the template
        placeholders = re.findall(r'\{(\w+)\}', cmd_def.command_template)
        
        # Check for required parameters
        for placeholder in placeholders:
            if placeholder not in parameters:
                raise ValueError(
                    f"Missing required parameter '{placeholder}' for command '{cmd_def.name}'. "
                    f"Expected parameters: {list(cmd_def.parameters.keys())}"
                )
        
        # Sanitize parameter values to prevent injection
        sanitized_params = {}
        for key, value in parameters.items():
            sanitized_params[key] = self._sanitize_parameter(value)
        
        # Build the command
        return cmd_def.command_template.format(**sanitized_params)
    
    def _sanitize_parameter(self, value: str) -> str:
        """
        Sanitize a parameter value to prevent command injection.
        
        Args:
            value: Raw parameter value
            
        Returns:
            Sanitized value safe for shell execution
            
        Raises:
            ValueError: If value contains dangerous characters
        """
        # Reject obviously dangerous patterns
        dangerous_patterns = [
            ';', '&&', '||', '|', '`', '$(',  # Command chaining/substitution
            '\n', '\r',  # Newlines
            '>', '<', '>>', '<<',  # Redirects
            '\\',  # Escape sequences
        ]
        
        for pattern in dangerous_patterns:
            if pattern in value:
                raise ValueError(
                    f"Parameter contains disallowed characters: '{pattern}'. "
                    f"For security, only alphanumeric characters, hyphens, "
                    f"underscores, dots, and forward slashes are allowed."
                )
        
        # Only allow safe characters
        if not re.match(r'^[a-zA-Z0-9._/-]+$', value):
            raise ValueError(
                f"Parameter '{value}' contains invalid characters. "
                f"Only alphanumeric characters, dots, hyphens, underscores, "
                f"and forward slashes are allowed."
            )
        
        return value
    
    async def test_connection(self) -> CommandResult:
        """
        Test the SSH connection by running 'echo connected'.
        
        Returns:
            CommandResult indicating if the connection works
        """
        return await self.run_command("echo 'SSH connection successful'")


# =============================================================================
# Convenience Functions
# =============================================================================

async def quick_command(
    config: SSHConfig,
    command_name: str,
    parameters: Optional[dict[str, str]] = None,
) -> CommandResult:
    """
    Execute a single whitelisted command without keeping connection open.
    
    Args:
        config: SSH configuration
        command_name: Name of whitelisted command
        parameters: Optional parameters
        
    Returns:
        CommandResult
    """
    async with SSHClient(config) as client:
        return await client.run_whitelisted_command(command_name, parameters)


async def test_ssh_connection(config: SSHConfig) -> tuple[bool, str]:
    """
    Test if SSH connection can be established.
    
    Args:
        config: SSH configuration
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        async with SSHClient(config) as client:
            result = await client.test_connection()
            if result.success:
                return True, f"Connected to {config.user}@{config.host}"
            else:
                return False, f"Connection test failed: {result.stderr}"
    except SSHClientError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


# =============================================================================
# CLI Testing
# =============================================================================

async def _test_main():
    """Test the SSH client from command line."""
    from .config import SSHConfig
    
    print("SSH Client Test")
    print("=" * 50)
    
    try:
        config = SSHConfig.from_env()
        print(f"Connecting to {config.user}@{config.host}:{config.port}...")
        
        success, message = await test_ssh_connection(config)
        
        if success:
            print(f"âœ… {message}")
            
            # Run some test commands
            async with SSHClient(config) as client:
                print("\nRunning test commands...")
                
                for cmd_name in ["whoami", "hostname", "uptime"]:
                    result = await client.run_whitelisted_command(cmd_name)
                    if result.success:
                        print(f"\n{cmd_name}:")
                        print(f"  {result.stdout.strip()}")
                    else:
                        print(f"\n{cmd_name}: FAILED")
                        print(f"  {result.error_message}")
        else:
            print(f"âŒ {message}")
            
    except ValueError as e:
        print(f"âŒ Configuration error: {e}")
    except Exception as e:
        print(f"âŒ Error: {e}")


if __name__ == "__main__":
    asyncio.run(_test_main())