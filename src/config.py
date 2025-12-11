"""
Phase 3: Configuration Models

Pydantic models for configuration, including remote server settings
and command whitelist definitions.
"""

import os
from pathlib import Path
from typing import Optional
from enum import Enum

import yaml
from pydantic import BaseModel, Field, field_validator, ConfigDict
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


class CommandCategory(str, Enum):
    """Categories of whitelisted commands."""
    SYSTEM = "system"
    DISK = "disk"
    NETWORK = "network"
    PROCESS = "process"
    SERVICE = "service"
    DOCKER = "docker"
    CUSTOM = "custom"


class SSHConfig(BaseModel):
    """Configuration for SSH connection to remote server."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    host: str = Field(
        ...,
        description="Remote server hostname or IP (use Tailscale IP for security)",
        min_length=1,
    )
    
    user: str = Field(
        ...,
        description="SSH username on the remote server",
        min_length=1,
    )
    
    port: int = Field(
        default=22,
        description="SSH port (default: 22)",
        ge=1,
        le=65535,
    )
    
    key_path: Optional[Path] = Field(
        default=None,
        description="Path to SSH private key file",
    )
    
    key_passphrase: Optional[str] = Field(
        default=None,
        description="Passphrase for encrypted SSH private key",
    )
    
    known_hosts_path: Optional[Path] = Field(
        default=None,
        description="Path to known_hosts file (default: ~/.ssh/known_hosts)",
    )
    
    connection_timeout: float = Field(
        default=10.0,
        description="Connection timeout in seconds",
        gt=0,
        le=60,
    )
    
    command_timeout: float = Field(
        default=30.0,
        description="Command execution timeout in seconds",
        gt=0,
        le=300,
    )
    
    @field_validator("key_path", "known_hosts_path", mode="before")
    @classmethod
    def expand_path(cls, v: Optional[str]) -> Optional[Path]:
        """Expand ~ and environment variables in paths."""
        if v is None:
            return None
        expanded = os.path.expanduser(os.path.expandvars(str(v)))
        return Path(expanded)
    
    @field_validator("key_path")
    @classmethod
    def validate_key_exists(cls, v: Optional[Path]) -> Optional[Path]:
        """Validate that the SSH key file exists."""
        if v is not None and not v.exists():
            raise ValueError(f"SSH key file not found: {v}")
        return v
    
    @classmethod
    def from_env(cls) -> "SSHConfig":
        """Create SSHConfig from environment variables."""
        host = os.getenv("REMOTE_HOST")
        user = os.getenv("REMOTE_USER")
        
        if not host:
            raise ValueError("REMOTE_HOST environment variable not set")
        if not user:
            raise ValueError("REMOTE_USER environment variable not set")
        
        # Get optional path values
        key_path_str = os.getenv("REMOTE_SSH_KEY_PATH")
        known_hosts_str = os.getenv("SSH_KNOWN_HOSTS_PATH")
        key_passphrase = os.getenv("REMOTE_SSH_KEY_PASSPHRASE")
        
        # Convert to Path if provided (validator will expand ~)
        key_path: Optional[Path] = Path(key_path_str) if key_path_str else None
        known_hosts_path: Optional[Path] = Path(known_hosts_str) if known_hosts_str else None
        
        return cls(
            host=host,
            user=user,
            port=int(os.getenv("REMOTE_SSH_PORT", "22")),
            key_path=key_path,
            key_passphrase=key_passphrase,
            known_hosts_path=known_hosts_path,
        )


class WhitelistedCommand(BaseModel):
    """Definition of a whitelisted command that can be executed remotely."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )
    
    name: str = Field(
        ...,
        description="Unique identifier for this command",
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    
    description: str = Field(
        ...,
        description="Human-readable description of what this command does",
        min_length=10,
        max_length=500,
    )
    
    command_template: str = Field(
        ...,
        description="Command template with optional {placeholders}",
        min_length=1,
    )
    
    category: CommandCategory = Field(
        default=CommandCategory.CUSTOM,
        description="Category of this command for organization",
    )
    
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Parameter descriptions for placeholders in command_template",
    )
    
    dangerous: bool = Field(
        default=False,
        description="Whether this command could be destructive",
    )
    
    requires_confirmation: bool = Field(
        default=False,
        description="Whether to require user confirmation before executing",
    )
    
    example_usage: Optional[str] = Field(
        default=None,
        description="Example of how to use this command",
    )


class AgentConfig(BaseModel):
    """Full configuration for the Tailscale MCP Agent."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    ssh: Optional[SSHConfig] = Field(
        default=None,
        description="SSH connection configuration",
    )
    
    anthropic_api_key: str = Field(
        ...,
        description="Anthropic API key for Claude",
        min_length=10,
    )
    
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use",
    )
    
    max_tokens: int = Field(
        default=4096,
        description="Maximum tokens in Claude's response",
        ge=100,
        le=8192,
    )
    
    ui_port: int = Field(
        default=7860,
        description="Port for the Gradio UI",
        ge=1024,
        le=65535,
    )
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create AgentConfig from environment variables."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        ssh_config: Optional[SSHConfig]
        try:
            ssh_config = SSHConfig.from_env()
        except ValueError:
            ssh_config = None

        return cls(
            ssh=ssh_config,
            anthropic_api_key=api_key,
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            ui_port=int(os.getenv("UI_PORT", "7860")),
        )


# =============================================================================
# Default Whitelisted Commands
# =============================================================================

DEFAULT_COMMANDS: list[WhitelistedCommand] = [
    # System Information
    WhitelistedCommand(
        name="hostname",
        description="Get the hostname of the remote server",
        command_template="hostname",
        category=CommandCategory.SYSTEM,
    ),
    WhitelistedCommand(
        name="uptime",
        description="Show how long the system has been running and load averages",
        command_template="uptime",
        category=CommandCategory.SYSTEM,
    ),
    WhitelistedCommand(
        name="whoami",
        description="Display the current user on the remote system",
        command_template="whoami",
        category=CommandCategory.SYSTEM,
    ),
    WhitelistedCommand(
        name="uname",
        description="Show system information including kernel version",
        command_template="uname -a",
        category=CommandCategory.SYSTEM,
    ),
    
    # Disk Usage
    WhitelistedCommand(
        name="disk_usage",
        description="Show disk space usage for all mounted filesystems",
        command_template="df -h",
        category=CommandCategory.DISK,
    ),
    WhitelistedCommand(
        name="disk_usage_path",
        description="Show disk usage for a specific path",
        command_template="du -sh {path}",
        category=CommandCategory.DISK,
        parameters={"path": "Path to check disk usage for (e.g., /var/log)"},
        example_usage="disk_usage_path with path=/var/log",
    ),
    
    # Memory
    WhitelistedCommand(
        name="memory_usage",
        description="Display memory usage in human-readable format",
        command_template="free -h",
        category=CommandCategory.SYSTEM,
    ),
    
    # Process Information
    WhitelistedCommand(
        name="top_processes",
        description="Show top 10 processes by CPU usage",
        command_template="ps aux --sort=-%cpu | head -11",
        category=CommandCategory.PROCESS,
    ),
    WhitelistedCommand(
        name="process_count",
        description="Count the total number of running processes",
        command_template="ps aux | wc -l",
        category=CommandCategory.PROCESS,
    ),
    
    # Network
    WhitelistedCommand(
        name="network_interfaces",
        description="List network interfaces and their IP addresses",
        command_template="ip addr show",
        category=CommandCategory.NETWORK,
    ),
    WhitelistedCommand(
        name="listening_ports",
        description="Show all listening TCP/UDP ports",
        command_template="ss -tulpn",
        category=CommandCategory.NETWORK,
    ),
    
    # Services (systemd)
    WhitelistedCommand(
        name="service_status",
        description="Check the status of a specific systemd service",
        command_template="systemctl status {service_name} --no-pager",
        category=CommandCategory.SERVICE,
        parameters={"service_name": "Name of the service (e.g., nginx, docker)"},
        example_usage="service_status with service_name=nginx",
    ),
    WhitelistedCommand(
        name="failed_services",
        description="List all failed systemd services",
        command_template="systemctl --failed --no-pager",
        category=CommandCategory.SERVICE,
    ),
    
    # Docker (if available)
    WhitelistedCommand(
        name="docker_ps",
        description="List running Docker containers",
        command_template="docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
        category=CommandCategory.DOCKER,
    ),
    WhitelistedCommand(
        name="docker_stats",
        description="Show Docker container resource usage (one snapshot)",
        command_template="docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'",
        category=CommandCategory.DOCKER,
    ),
]


def get_command_by_name(name: str) -> Optional[WhitelistedCommand]:
    """Look up a whitelisted command by name."""
    for cmd in get_whitelisted_commands():
        if cmd.name == name:
            return cmd
    return None


def get_commands_by_category(category: CommandCategory) -> list[WhitelistedCommand]:
    """Get all commands in a specific category."""
    return [cmd for cmd in get_whitelisted_commands() if cmd.category == category]


_cached_commands: Optional[list[WhitelistedCommand]] = None
_commands_path: Optional[Path] = None


def _parse_commands_yaml(path: Path) -> list[WhitelistedCommand]:
    """Load whitelisted commands from a YAML file."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_commands = data.get("commands", [])
    commands: list[WhitelistedCommand] = []

    for raw in raw_commands:
        category_value = raw.get("category", CommandCategory.CUSTOM.value)
        try:
            category = CommandCategory(category_value.lower())
        except ValueError as exc:
            raise ValueError(
                f"Invalid category '{category_value}' in {path} for command '{raw.get('name')}'"
            ) from exc

        commands.append(
            WhitelistedCommand(
                name=raw["name"],
                description=raw["description"],
                command_template=raw["command_template"],
                category=category,
                parameters=raw.get("parameters", {}),
                dangerous=raw.get("dangerous", False),
                requires_confirmation=raw.get("requires_confirmation", False),
                example_usage=raw.get("example_usage"),
            )
        )

    return commands


def get_whitelisted_commands(path: Optional[Path] = None) -> list[WhitelistedCommand]:
    """Return whitelisted commands, preferring YAML configuration when available."""
    global _cached_commands, _commands_path

    yaml_path = path or Path(__file__).resolve().parent.parent / "config" / "commands.yaml"

    if _cached_commands is not None and _commands_path == yaml_path:
        return list(_cached_commands)

    if yaml_path.exists():
        try:
            commands = _parse_commands_yaml(yaml_path)
            _cached_commands = commands
            _commands_path = yaml_path
            return list(commands)
        except Exception:
            # Fall back to defaults if YAML is invalid
            pass

    _cached_commands = list(DEFAULT_COMMANDS)
    _commands_path = None
    return list(DEFAULT_COMMANDS)