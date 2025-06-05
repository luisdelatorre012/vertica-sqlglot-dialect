#!/usr/bin/env python3
"""
Verify Project Metadata using tomllib (Python 3.11+)

This script demonstrates the use of the `tomllib` standard library module,
introduced in Python 3.11, to parse the `pyproject.toml` file and verify
its contents.
"""

import tomllib
from pathlib import Path

def verify_project_metadata():
    """
    Reads pyproject.toml, parses it, and prints key metadata.
    """
    print("=" * 60)
    print("VERIFYING PROJECT METADATA WITH TOMLIB")
    print("=" * 60)

    try:
        # Construct the path to pyproject.toml relative to this script
        # This makes the script runnable from any directory
        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"

        if not pyproject_path.exists():
            print(f"Error: pyproject.toml not found at {pyproject_path}")
            return

        with open(pyproject_path, "rb") as f:
            # tomllib.load requires a binary file handle
            data = tomllib.load(f)

        # Access and print project metadata
        project_meta = data.get("project", {})
        project_name = project_meta.get("name")
        project_version = project_meta.get("version")
        project_description = project_meta.get("description")
        python_requires = project_meta.get("requires-python")

        print(f"Successfully parsed {pyproject_path.name}:")
        print(f"  - Project Name:    {project_name}")
        print(f"  - Version:         {project_version}")
        print(f"  - Description:     {project_description}")
        print(f"  - Python Requires: {python_requires}")
        
        # Verification check
        if python_requires and python_requires == ">=3.11":
            print("\n✅ Verification PASSED: 'requires-python' is set correctly for Python 3.11+ features.")
        else:
            print(f"\n❌ Verification FAILED: 'requires-python' is '{python_requires}', but should be '>=3.11'.")

    except tomllib.TOMLDecodeError as e:
        print(f"Error parsing pyproject.toml: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    verify_project_metadata() 