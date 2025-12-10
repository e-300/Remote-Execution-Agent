"""
Dependency Check

Run this script to verify all dependencies are installed correctly:
    python check_setup.py

If any dependencies are missing, install them with:
    pip install -r requirements.txt
"""

import sys

def check_import(module_name: str, package_name: str = "") -> bool:
    """Try to import a module and report status."""
    package_name = package_name or module_name
    try:
        __import__(module_name)
        print(f"  ✅ {package_name}")
        return True
    except ImportError as e:
        print(f"  ❌ {package_name} - {e}")
        return False


def main():
    print("Checking Tailscale MCP Agent dependencies...\n")
    
    all_ok = True
    
    print("Core dependencies:")
    all_ok &= check_import("gradio")
    all_ok &= check_import("anthropic")
    all_ok &= check_import("asyncssh")
    all_ok &= check_import("pydantic")
    all_ok &= check_import("mcp")
    all_ok &= check_import("httpx")
    all_ok &= check_import("dotenv", "python-dotenv")
    all_ok &= check_import("yaml", "pyyaml")
    
    print("\nOptional (for testing):")
    check_import("pytest")
    check_import("pytest_asyncio", "pytest-asyncio")
    
    print()
    
    if all_ok:
        print("✅ All core dependencies installed!")
        print("\nYou can now run the agent with:")
        print("  python run.py")
        return 0
    else:
        print("❌ Some dependencies are missing!")
        print("\nInstall them with:")
        print("  pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())