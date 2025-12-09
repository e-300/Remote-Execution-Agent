from enum import Enum
from pydantic import BaseModel, Field


class RemoteTarget(BaseModel):
    name: str = Field(..., description="Logical name of the server")
    hostname: str = Field(..., description="IP or DNS (Tailscale or LAN)")
    username: str = Field(..., description="SSH username")
    ssh_key_path: str = Field(..., description="Path to private key")
    role: str | None = Field(None, description="Role, e.g. web, db")
    env: str | None = Field(None, description="Environment, e.g. lab, prod")


class CommandName(str, Enum):
    CHECK_DISK = "check_disk"
    CHECK_LOAD = "check_load"
    CHECK_MEM = "check_mem"
    CHECK_UPTIME = "check_uptime"


COMMAND_MAP: dict[CommandName, str] = {
    CommandName.CHECK_DISK: "df -h",
    CommandName.CHECK_LOAD: "uptime",
    CommandName.CHECK_MEM: "free -h",
    CommandName.CHECK_UPTIME: "uptime -p",
}

