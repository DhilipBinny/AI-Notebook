
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Ensure Anthropic API key is set (mock if needed for structure test, but real key needed for actual call)
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("WARNING: ANTHROPIC_API_KEY not found in environment. Tests will fail if not mocked.")

try:
    from backend.llm_client_anthropic import AnthropicClient
    print("✅ Successfully imported AnthropicClient")
except ImportError as e:
    print(f"❌ Failed to import AnthropicClient: {e}")
    sys.exit(1)

def test_client_init():
    try:
        # Initialize with dummy key if not present, just to test class structure
        api_key = os.environ.get("ANTHROPIC_API_KEY", "dummy_key")
        client = AnthropicClient(api_key=api_key)
        print("✅ Successfully initialized AnthropicClient")
        return client
    except Exception as e:
        print(f"❌ Failed to initialize AnthropicClient: {e}")
        return None

def test_provider_name(client):
    if client.provider_name == "Anthropic":
        print("✅ Provider name is correct")
    else:
        print(f"❌ Provider name is incorrect: {client.provider_name}")

if __name__ == "__main__":
    print("Running Anthropic Client Verification...")
    client = test_client_init()
    if client:
        test_provider_name(client)
        # We can't easily test actual API calls without a valid key and network, 
        # but we've verified the code structure and imports.
