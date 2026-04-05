# test_cli_meeting.py
import subprocess
import os

def test_cli_meeting_help():
    # Run cli.py meeting --help and check for description
    result = subprocess.run(["python3", "cli.py", "meeting", "--help"], capture_output=True, text=True)
    assert "Extract decisions from a meeting transcript" in result.stdout

if __name__ == "__main__":
    try:
        test_cli_meeting_help()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
