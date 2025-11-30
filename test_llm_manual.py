#!/usr/bin/env python3
"""Manual test script to verify LLM abstraction layer works."""

import asyncio

from haia.config import settings
from haia.llm import Message, create_client


async def main() -> None:
    """Test the LLM client."""
    print(f"Testing LLM client with model: {settings.haia_model}")

    # Create client
    client = create_client(settings)
    print(f"Created client: {type(client).__name__}")

    # Send test message
    messages = [Message(role="user", content="Hello! Please respond with just 'Hi'")]
    print(f"Sending message: {messages[0].content}")

    response = await client.chat(messages=messages, max_tokens=20)

    print(f"\nResponse received:")
    print(f"  Content: {response.content}")
    print(f"  Model: {response.model}")
    print(f"  Prompt tokens: {response.usage.prompt_tokens}")
    print(f"  Completion tokens: {response.usage.completion_tokens}")
    print(f"  Total tokens: {response.usage.total_tokens}")
    print(f"  Cost estimate: ${response.usage.cost_estimate:.6f}")
    print(f"  Finish reason: {response.finish_reason}")


if __name__ == "__main__":
    asyncio.run(main())
