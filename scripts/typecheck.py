#!/usr/bin/env python3
"""
Standalone type checking script for SAGA Graph.
Runs MyPy with proper configuration and provides clear output.
"""
import subprocess
import sys
import os
from pathlib import Path

def main() -> int:
    """Run MyPy type checking on the project."""
    
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("🔍 Running MyPy type checking...")
    print(f"📁 Project root: {project_root}")
    
    # Define modules to check with strict typing
    strict_modules = [
        "graph_db/",
        "utils/", 
        "main.py",
        "user_anchor_nodes.py"
    ]
    
    # Find all LLM helper modules
    llm_modules = list(project_root.glob("**/*_llm.py"))
    llm_paths = [str(p.relative_to(project_root)) for p in llm_modules]
    
    # Combine all modules to check
    modules_to_check = strict_modules + llm_paths
    
    # Filter to existing paths only
    existing_modules = []
    for module in modules_to_check:
        if (project_root / module).exists():
            existing_modules.append(module)
        else:
            print(f"⚠️  Module not found: {module}")
    
    if not existing_modules:
        print("❌ No modules found to type check!")
        return 1
    
    print(f"📝 Type checking {len(existing_modules)} modules:")
    for module in existing_modules[:5]:  # Show first 5
        print(f"   - {module}")
    if len(existing_modules) > 5:
        print(f"   ... and {len(existing_modules) - 5} more")
    
    # Run MyPy
    cmd = [
        sys.executable, "-m", "mypy",
        "--config-file", "config/mypy.ini",
        "--show-error-codes",
        "--pretty"
    ] + existing_modules
    
    print(f"\n🚀 Running: {' '.join(cmd[:4])} ... {len(existing_modules)} modules")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.stdout:
            print("\n📊 MyPy Output:")
            print(result.stdout)
        
        if result.stderr:
            print("\n⚠️  MyPy Warnings/Errors:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Type checking passed! All modules are properly typed.")
            return 0
        else:
            print(f"\n❌ Type checking failed with exit code {result.returncode}")
            print("💡 Fix the type errors above and run again.")
            return result.returncode
            
    except subprocess.TimeoutExpired:
        print("❌ Type checking timed out after 60 seconds")
        return 1
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to run MyPy: {e}")
        return 1
    except FileNotFoundError:
        print("❌ MyPy not found. Install with: pip install mypy")
        return 1

def check_mypy_installed() -> bool:
    """Check if MyPy is installed and accessible."""
    try:
        result = subprocess.run([sys.executable, "-m", "mypy", "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"📦 MyPy version: {version}")
            return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    print("❌ MyPy not installed or not accessible")
    print("💡 Install with: pip install mypy")
    return False

if __name__ == "__main__":
    print("🎯 SAGA Graph Type Checker")
    print("=" * 50)
    
    if not check_mypy_installed():
        sys.exit(1)
    
    exit_code = main()
    
    if exit_code == 0:
        print("\n🎉 All type checks passed!")
    else:
        print(f"\n💥 Type checking failed (exit code: {exit_code})")
    
    sys.exit(exit_code)