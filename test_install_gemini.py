# test_install.py
import install
import os
from unittest.mock import patch, MagicMock

def test_gemini_wrapper_generation():
    # Test that gemini wrapper is part of the output
    # We'll mock the Path.home and check if wrapper_content contains 'gemini()'
    
    # This is a bit tricky because install_shell_wrappers writes to files.
    # We can mock the write_text call.
    
    with patch('pathlib.Path.write_text') as mock_write:
        with patch('platform.system', return_value='Darwin'):
            with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
                install.install_shell_wrappers()
                # Check if any call to write_text contained the new 'gemini()' logic
                found = False
                for call in mock_write.call_args_list:
                    content = call[0][0]
                    if 'gemini() {' in content and 'output=$(command gemini "$@")' in content:
                        found = True
                        break
                assert found, "New detailed Gemini wrapper not found in shell wrappers"

if __name__ == "__main__":
    try:
        test_gemini_wrapper_generation()
        print("Test Passed")
    except AssertionError as e:
        print(f"Test Failed: {e}")
    except Exception as e:
        print(f"Error: {e}")
