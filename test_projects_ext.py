# test_projects_ext.py
import projects
import os
import shutil
from pathlib import Path

def test_project_metadata_management():
    proj_path = "/tmp/test_keel_proj"
    # Ensure directory exists for metadata logic
    os.makedirs(proj_path, exist_ok=True)
    
    try:
        # Set some metadata
        projects.set_project_metadata(proj_path, archived=True, confidential=True)
        
        # Get it back
        meta = projects.get_project_metadata(proj_path)
        
        assert meta["archived"] is True
        assert meta["confidential"] is True
        
        # Toggle back
        projects.set_project_metadata(proj_path, archived=False, confidential=False)
        meta = projects.get_project_metadata(proj_path)
        assert meta["archived"] is False
        assert meta["confidential"] is False
        
    finally:
        if os.path.exists(proj_path):
            shutil.rmtree(proj_path)

if __name__ == "__main__":
    try:
        test_project_metadata_management()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
