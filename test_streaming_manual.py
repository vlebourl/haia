#!/usr/bin/env python3
"""Manual test script for streaming API.

Start the server first with: uv run python -m haia.main
Then run this script with: python test_streaming_manual.py
"""

import json

import httpx


def test_streaming():
    """Test streaming chat completion."""
    url = "http://localhost:8000/v1/chat/completions"

    payload = {
        "model": "haia",
        "messages": [
            {"role": "user", "content": "What is Docker? Explain in 2-3 sentences."}
        ],
        "stream": True,
    }

    print("🚀 Testing streaming API...")
    print(f"📤 Sending request to {url}")
    print(f"📝 Prompt: {payload['messages'][0]['content']}\n")

    try:
        with httpx.stream("POST", url, json=payload, timeout=30.0) as response:
            print(f"✅ Status: {response.status_code}")
            print(f"📋 Content-Type: {response.headers.get('content-type')}\n")

            if response.status_code != 200:
                print(f"❌ Error: {response.text}")
                return

            print("📡 Streaming response:\n")
            print("-" * 60)

            accumulated = ""
            chunk_count = 0

            for line in response.iter_lines():
                if not line:
                    continue

                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix

                    if data == "[DONE]":
                        print("\n" + "-" * 60)
                        print("✅ Stream complete!")
                        break

                    try:
                        chunk = json.loads(data)
                        chunk_count += 1

                        # Extract content from delta
                        if chunk.get("choices"):
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                print(content, end="", flush=True)
                                accumulated += content

                            # Check for finish_reason
                            finish_reason = chunk["choices"][0].get("finish_reason")
                            if finish_reason:
                                print(f"\n\n🏁 Finish reason: {finish_reason}")

                            # Check for usage stats
                            if "usage" in chunk:
                                usage = chunk["usage"]
                                print(f"📊 Usage: {usage['total_tokens']} tokens "
                                      f"({usage['prompt_tokens']} prompt + "
                                      f"{usage['completion_tokens']} completion)")

                    except json.JSONDecodeError as e:
                        print(f"\n⚠️  Failed to parse chunk: {e}")

            print(f"\n\n📦 Received {chunk_count} chunks")
            print(f"📏 Total length: {len(accumulated)} characters")

    except httpx.ConnectError:
        print("❌ Connection failed. Is the server running?")
        print("   Start it with: uv run python -m haia.main")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_non_streaming():
    """Test non-streaming for comparison."""
    url = "http://localhost:8000/v1/chat/completions"

    payload = {
        "model": "haia",
        "messages": [
            {"role": "user", "content": "What is Docker? Explain in 2-3 sentences."}
        ],
        "stream": False,
    }

    print("\n\n🚀 Testing non-streaming API (for comparison)...")

    try:
        response = httpx.post(url, json=payload, timeout=30.0)

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data["usage"]

            print(f"✅ Status: {response.status_code}")
            print(f"\n📝 Response:\n{content}")
            print(f"\n📊 Usage: {usage['total_tokens']} tokens")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")

    except httpx.ConnectError:
        print("❌ Connection failed. Is the server running?")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_streaming()
    test_non_streaming()
