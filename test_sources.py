import sources
import os
from pathlib import Path

def test_get_status():
    status = sources.get_status()
    assert "manual" in status
    assert status["manual"]["installed"] is True
    assert "git" in status

def test_enable_disable():
    sources.set_enabled("gemini", False)
    status = sources.get_status()
    assert status["gemini"]["enabled"] is False
    
    sources.set_enabled("gemini", True)
    status = sources.get_status()
    assert status["gemini"]["enabled"] is True

def test_test_source():
    # manual should always pass test as it just writes to queue
    assert sources.test_source("manual") is True

if __name__ == "__main__":
    test_get_status()
    test_enable_disable()
    test_test_source()
    print("Sources Tests Passed")
