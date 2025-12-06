#!/usr/bin/env python3
"""
Test script for LLM image support.

Usage:
    # From playground directory:
    python test_image_support.py

    # Or with a specific image:
    python test_image_support.py /path/to/image.png

This script tests the image encoding and LLM client functionality.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.llm_clients import (
    LLMClient,
    encode_image_from_path,
    encode_image_from_bytes,
    prepare_image,
)


def test_image_utilities():
    """Test image encoding utilities"""
    print("=" * 60)
    print("Testing Image Utilities")
    print("=" * 60)

    # Test 1: encode_image_from_bytes
    print("\n1. Testing encode_image_from_bytes...")
    test_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'  # PNG header
    result = encode_image_from_bytes(test_bytes, "image/png")
    assert "data" in result
    assert "mime_type" in result
    assert result["mime_type"] == "image/png"
    print(f"   ✅ Result: data={result['data'][:20]}..., mime_type={result['mime_type']}")

    # Test 2: prepare_image with base64 data
    print("\n2. Testing prepare_image with base64 data...")
    img = {"data": "dGVzdGRhdGE=", "mime_type": "image/jpeg"}
    result = prepare_image(img)
    assert result["data"] == "dGVzdGRhdGE="
    assert result["mime_type"] == "image/jpeg"
    print(f"   ✅ Result: {result}")

    # Test 3: prepare_image with URL
    print("\n3. Testing prepare_image with URL...")
    img = {"url": "https://example.com/image.png"}
    result = prepare_image(img)
    assert "url" in result
    print(f"   ✅ Result: {result}")

    # Test 4: prepare_image with path (will fail if file doesn't exist)
    print("\n4. Testing prepare_image with file path...")
    try:
        img = {"path": "/nonexistent/file.png"}
        prepare_image(img)
        print("   ❌ Should have raised FileNotFoundError")
    except FileNotFoundError as e:
        print(f"   ✅ Correctly raised FileNotFoundError: {e}")

    print("\n" + "=" * 60)
    print("✅ All utility tests passed!")
    print("=" * 60)


def test_llm_with_image(image_path: str = None):
    """Test LLM client with an image"""
    print("\n" + "=" * 60)
    print("Testing LLM Client with Image")
    print("=" * 60)

    if not image_path:
        # Create a simple test image (1x1 red pixel PNG)
        import base64
        # Minimal valid PNG (1x1 red pixel)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIA"
            "X8jx0gAAAABJRU5ErkJggg=="
        )
        image = encode_image_from_bytes(png_data, "image/png")
        print("\n📷 Using test image: 1x1 red pixel PNG")
    else:
        if not os.path.exists(image_path):
            print(f"❌ Image file not found: {image_path}")
            return
        image = encode_image_from_path(image_path)
        print(f"\n📷 Using image: {image_path}")
        print(f"   Size: {len(image['data'])} bytes (base64)")
        print(f"   Type: {image['mime_type']}")

    # Check if LLM provider is configured
    import backend.config as cfg
    print(f"\n🤖 LLM Provider: {cfg.LLM_PROVIDER}")

    # Check for API keys
    if cfg.LLM_PROVIDER == "anthropic" and not cfg.ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set")
        return
    elif cfg.LLM_PROVIDER == "openai" and not cfg.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set")
        return
    elif cfg.LLM_PROVIDER == "gemini" and not cfg.GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set")
        return
    elif cfg.LLM_PROVIDER == "ollama":
        print(f"   Ollama URL: {cfg.OLLAMA_URL}")
        print(f"   Ollama Model: {cfg.OLLAMA_MODEL}")
        print("   ⚠️  Note: Image support requires a vision model (llava, bakllava)")

    try:
        client = LLMClient()
        print(f"\n📤 Sending request to {client.provider_name}...")

        # Test ai_cell_completion with image
        response = client.ai_cell_completion(
            "Describe this image briefly. What do you see?",
            images=[image]
        )

        print(f"\n📥 Response ({len(response)} chars):")
        print("-" * 40)
        print(response[:500] + ("..." if len(response) > 500 else ""))
        print("-" * 40)
        print("\n✅ LLM image test passed!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    # Run utility tests
    test_image_utilities()

    # Check for image argument
    image_path = sys.argv[1] if len(sys.argv) > 1 else None

    # Run LLM test
    print("\n" + "=" * 60)
    print("Do you want to test with actual LLM? (requires API key)")
    print("=" * 60)

    response = input("Test LLM with image? [y/N]: ").strip().lower()
    if response == 'y':
        test_llm_with_image(image_path)
    else:
        print("Skipping LLM test.")

    print("\n✅ All tests completed!")


if __name__ == "__main__":
    main()
