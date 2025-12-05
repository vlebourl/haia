"""Personal homelab profile loading and management.

Loads homelab-specific information from YAML profile files
and converts them into system prompt context.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProxmoxHost(BaseModel):
    """Proxmox host configuration."""

    name: str = Field(..., description="Host name")
    ip: str = Field(..., description="IP address")
    role: str | None = Field(None, description="Role (e.g., primary, secondary)")


class VM(BaseModel):
    """Virtual machine or LXC container configuration."""

    name: str = Field(..., description="VM/LXC name")
    id: int = Field(..., description="VM/LXC ID")
    type: str | None = Field(None, description="Type: VM or LXC")
    host: str | None = Field(None, description="Proxmox host where this runs")
    description: str | None = Field(None, description="VM/LXC description")
    docker_services: list[str] = Field(
        default_factory=list, description="Docker containers running inside this VM/LXC"
    )


class ProxmoxConfig(BaseModel):
    """Proxmox cluster configuration."""

    hosts: list[ProxmoxHost] = Field(default_factory=list)
    important_vms: list[VM] = Field(default_factory=list)


class NetworkConfig(BaseModel):
    """Network configuration."""

    subnets: list[str] = Field(default_factory=list)


class HomelabProfile(BaseModel):
    """Personal homelab profile."""

    name: str = Field("My Homelab", description="Homelab name")
    proxmox: ProxmoxConfig | None = None
    network: NetworkConfig | None = None
    preferences: list[str] = Field(default_factory=list)
    custom_instructions: str = ""


def load_profile(profile_path: str | Path) -> HomelabProfile | None:
    """Load homelab profile from YAML file.

    Args:
        profile_path: Path to YAML profile file

    Returns:
        HomelabProfile if file exists and is valid, None otherwise
    """
    path = Path(profile_path)

    if not path.exists():
        logger.debug(f"Profile file not found: {path}")
        return None

    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or "homelab" not in data:
            logger.warning(f"Invalid profile format in {path}: missing 'homelab' key")
            return None

        profile = HomelabProfile(**data["homelab"])
        logger.info(f"Loaded homelab profile: {profile.name}")
        return profile

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML profile {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load profile {path}: {e}")
        return None


def profile_to_prompt(profile: HomelabProfile) -> str:
    """Convert homelab profile to system prompt context.

    Args:
        profile: Homelab profile

    Returns:
        Formatted string to append to system prompt
    """
    sections = []

    sections.append(f"## Homelab Context: {profile.name}")

    # Proxmox hosts
    if profile.proxmox and profile.proxmox.hosts:
        sections.append("\n### Proxmox Hosts:")
        for host in profile.proxmox.hosts:
            role = f" ({host.role})" if host.role else ""
            sections.append(f"- {host.name}: {host.ip}{role}")

    # Important VMs and LXCs
    if profile.proxmox and profile.proxmox.important_vms:
        sections.append("\n### VMs and LXC Containers:")
        for vm in profile.proxmox.important_vms:
            # Build the entry line with type and host if available
            vm_type = f" [{vm.type}]" if vm.type else ""
            host_info = f" on {vm.host}" if vm.host else ""
            desc = f" - {vm.description}" if vm.description else ""
            sections.append(f"- {vm.name} (ID: {vm.id}){vm_type}{host_info}{desc}")

            # Add Docker services if present
            if vm.docker_services:
                sections.append("  Docker services:")
                for service in vm.docker_services:
                    sections.append(f"    - {service}")

    # Network
    if profile.network and profile.network.subnets:
        sections.append("\n### Network Subnets:")
        for subnet in profile.network.subnets:
            sections.append(f"- {subnet}")

    # Preferences
    if profile.preferences:
        sections.append("\n### User Preferences:")
        for pref in profile.preferences:
            sections.append(f"- {pref}")

    # Custom instructions
    if profile.custom_instructions:
        sections.append("\n### Additional Instructions:")
        sections.append(profile.custom_instructions)

    return "\n".join(sections)


def load_profile_context(profile_path: str | Path) -> str:
    """Load profile and convert to prompt context.

    Args:
        profile_path: Path to YAML profile file

    Returns:
        Formatted context string (empty if no profile)
    """
    profile = load_profile(profile_path)
    if profile is None:
        return ""

    return profile_to_prompt(profile)
