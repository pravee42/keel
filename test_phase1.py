#!/usr/bin/env python3
"""Phase 1 integration test: Event capture, extraction, and cross-platform support."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import platform_utils
    KEEL_HOME = platform_utils.get_keel_home()
except ImportError:
    KEEL_HOME = Path.home() / ".keel"

QUEUE_PATH = KEEL_HOME / "queue.jsonl"
SCRIPT_DIR = Path(__file__).parent.resolve()


def test_queue_writer():
    """Test queue_writer.py captures all 7 sources."""
    print("\n[TEST 1] queue_writer: all 7 sources + prompt/output")
    sources = [
        ("copilot", "Write hello", "print()"),
        ("gemini", "What is Python?", "A language"),
        ("cursor", "Refactor", "refactored"),
        ("antigravity", "Test", "def test()"),
        ("claude-code", "Fix bug", "Fixed"),
        ("git", "Initial", "Added"),
        ("manual", "Log", ""),
    ]
    
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.unlink(missing_ok=True)
    
    for source, prompt, output in sources:
        cmd = [sys.executable, str(SCRIPT_DIR / "queue_writer.py"),
               "--source", source, "--prompt", prompt, "--output", output,
               "--type", "prompt", "--cwd", str(os.getcwd())]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ✗ {source}: {result.stderr[:100]}")
            return False
    
    # Verify queue
    with open(QUEUE_PATH) as f:
        lines = f.readlines()
    
    if len(lines) != len(sources):
        print(f"  ✗ Expected {len(sources)} events, got {len(lines)}")
        return False
    
    print(f"  ✓ All 7 sources captured ({QUEUE_PATH})")
    return True


def test_processor():
    """Test processor.py extraction."""
    print("[TEST 2] processor: prompt/output extraction")
    try:
        import processor
        # Test git
        git_text = "COMMIT: Init\n\nCHANGED FILES:\nfile.py"
        p, o = processor._split_prompt_output(git_text, "git")
        if "Init" not in p or "file.py" not in o:
            print(f"  ✗ Git extraction failed: p={repr(p)}, o={repr(o)}")
            return False
        print("  ✓ Git extraction works")
        return True
    except Exception as e:
        print(f"  ✗ {e}")
        return False


def test_platform_utils():
    """Test platform_utils."""
    print("[TEST 3] platform_utils: cross-platform paths")
    try:
        import platform_utils
        home = platform_utils.get_keel_home()
        print(f"  ✓ KEEL_HOME: {home}")
        return True
    except Exception as e:
        print(f"  ✗ {e}")
        return False


def test_decision_fields():
    """Test Decision has new fields."""
    print("[TEST 4] store.Decision: source_tool + prompt + output")
    try:
        import store
        d = store.Decision(
            id="t1", timestamp=datetime.utcnow().isoformat(), domain="code",
            title="T", context="", options="", choice="", reasoning="",
            principles="[]", outcome="", tags="[]", paths="[]", project="",
            outcome_quality="", source_tool="copilot", prompt="p", output="o"
        )
        assert d.source_tool == "copilot"
        assert d.prompt == "p"
        assert d.output == "o"
        print("  ✓ New fields present and working")
        return True
    except Exception as e:
        print(f"  ✗ {e}")
        return False


def test_tool_injector():
    """Test tool_injector."""
    print("[TEST 5] tool_injector: multi-tool injection")
    try:
        import tool_injector
        print("  ✓ tool_injector module loaded")
        return True
    except ImportError:
        print("  ⊘ tool_injector not available")
        return False


def main():
    print("\n" + "=" * 60)
    print("Phase 1.1 - Phase 1.3 Integration Tests")
    print("=" * 60)
    
    tests = [
        test_queue_writer,
        test_processor,
        test_platform_utils,
        test_decision_fields,
        test_tool_injector,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
