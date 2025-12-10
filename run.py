#!/usr/bin/env python3
"""
Tailscale MCP Agent - Startup Script

This script validates configuration and launches the agent.
Run this to start the full system.

Usage:
    python run.py
    
    # Or make it executable and run directly
    chmod +x run.py
    ./run.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv


def print_banner():
    """Print startup banner."""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   🔐 Tailscale MCP Agent                                          ║
║                                                                   ║
║   Execute remote commands via Claude + SSH + Tailscale            ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)


def check_env_file() -> bool:
    """Check if .env file exists."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("❌ .env file not found!")
        print()
        print("   Please create a .env file with your configuration:")
        print("   cp .env.example .env")
        print("   Then edit .env with your values.")
        return False
    return True


def check_anthropic_key() -> bool:
    """Check if Anthropic API key is configured."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("❌ ANTHROPIC_API_KEY not set!")
        print()
        print("   Add your API key to .env:")
        print("   ANTHROPIC_API_KEY=sk-ant-...")
        return False
    
    if key.startswith("sk-ant-") or len(key) > 20:
        print("✅ Anthropic API key configured")
        return True
    else:
        print("⚠️  ANTHROPIC_API_KEY looks invalid")
        return True  # Continue anyway, will fail on actual API call


def check_ssh_config() -> bool:
    """Check if SSH configuration is valid."""
    host = os.getenv("REMOTE_HOST")
    user = os.getenv("REMOTE_USER")
    key_path = os.getenv("REMOTE_SSH_KEY_PATH")
    
    if not host:
        print("⚠️  REMOTE_HOST not set (SSH commands will fail)")
        return False
    
    if not user:
        print("⚠️  REMOTE_USER not set (SSH commands will fail)")
        return False
    
    print(f"✅ SSH configured: {user}@{host}")
    
    if key_path:
        key_file = Path(os.path.expanduser(key_path))
        if key_file.exists():
            print(f"✅ SSH key found: {key_path}")
        else:
            print(f"⚠️  SSH key not found: {key_path}")
            return False
    else:
        print("⚠️  REMOTE_SSH_KEY_PATH not set (will use default key)")
    
    return True


async def test_ssh_connection() -> bool:
    """Test SSH connection to remote server."""
    try:
        from src.config import SSHConfig
        from src.ssh_client import test_ssh_connection as ssh_test
        
        config = SSHConfig.from_env()
        print(f"\n   Testing SSH connection to {config.user}@{config.host}...")
        
        success, message = await ssh_test(config)
        
        if success:
            print(f"   ✅ SSH connection successful!")
            return True
        else:
            print(f"   ❌ SSH connection failed: {message}")
            return False
            
    except ValueError as e:
        print(f"   ⚠️  Cannot test SSH: {e}")
        return False
    except Exception as e:
        print(f"   ❌ SSH test error: {e}")
        return False


def main():
    """Main entry point."""
    print_banner()
    
    # Load environment
    load_dotenv()
    
    print("Checking configuration...\n")
    
    # Check requirements
    env_ok = check_env_file()
    if not env_ok:
        sys.exit(1)
    
    # Reload after confirming .env exists
    load_dotenv(override=True)
    
    api_ok = check_anthropic_key()
    ssh_ok = check_ssh_config()
    
    print()
    
    # Test SSH if configured
    if ssh_ok:
        ssh_test_ok = asyncio.run(test_ssh_connection())
    else:
        ssh_test_ok = False
        print("\n   Skipping SSH test (not fully configured)")
    
    print()
    
    if not api_ok:
        print("❌ Cannot start: Anthropic API key required")
        sys.exit(1)
    
    if not ssh_ok or not ssh_test_ok:
        print("⚠️  Starting without SSH connection")
        print("   You can still chat with Claude, but remote commands will fail.")
        print("   Configure SSH settings in .env to enable remote execution.")
    
    print()
    print("=" * 60)
    print()
    print("Starting Gradio UI...")
    print()
    print("   Local URL:     http://localhost:7860")
    print("   Tailscale URL: http://<your-tailscale-ip>:7860")
    print()
    print("   Press Ctrl+C to stop")
    print()
    
    # Import and run the chat UI
    from src.chat_ui import main as run_chat
    run_chat()


if __name__ == "__main__":
    main()