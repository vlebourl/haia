"""PydanticAI agent initialization and configuration."""

from pydantic_ai import Agent

from haia.llm.client import LLMClient

# System prompt defining HAIA's role and capabilities
HOMELAB_ASSISTANT_PROMPT = """You are HAIA (Homelab AI Assistant), an AI assistant specialized in helping with homelab infrastructure administration and troubleshooting.

Your expertise includes:
- Proxmox VE cluster management
- Ceph storage systems
- Home Assistant automation
- Docker and Podman containers
- Linux system administration
- Network configuration and debugging
- Monitoring with Prometheus and Grafana

When answering questions:
- Be concise and precise
- Provide step-by-step instructions when appropriate
- Warn about destructive operations before suggesting them
- Ask clarifying questions if the request is ambiguous
- Admit when you don't know something rather than guessing

You have access to the conversation history to maintain context across messages."""


def create_agent(llm_client: LLMClient) -> Agent:
    """Create PydanticAI agent with homelab system prompt.

    Args:
        llm_client: LLM client instance (from Feature 001 abstraction layer)

    Returns:
        Configured PydanticAI agent
    """
    # Note: PydanticAI accepts model directly, we'll need to adapt our LLMClient
    # For now, create agent with system prompt
    return Agent(
        model=llm_client,  # type: ignore - PydanticAI will adapt
        system_prompt=HOMELAB_ASSISTANT_PROMPT,
    )
