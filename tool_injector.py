"""Route per-project decisions to tool-specific instruction files.

Supports:
- .cursorrules (Cursor editor)
- .windsurfrules (Windsurf editor)
- .clinerules (Claude CLI)
- .copilot-instructions.md (GitHub Copilot)
- CLAUDE.md (Claude Code)

Each tool gets a project context block injected using markers.
"""

import re
from pathlib import Path
from typing import Optional, Dict, List

from store import Decision

MARKER_START = "<!-- keel:project:start -->"
MARKER_END = "<!-- keel:project:end -->"

# Tool-specific file configurations
TOOL_TARGETS = {
    "cursor": {
        "filename": ".cursorrules",
        "is_markdown": False,  # Rules file format
        "marker_style": "comment",
    },
    "windsurf": {
        "filename": ".windsurfrules",
        "is_markdown": False,
        "marker_style": "comment",
    },
    "claude-cli": {
        "filename": ".clinerules",
        "is_markdown": False,
        "marker_style": "comment",
    },
    "copilot": {
        "filename": ".copilot-instructions.md",
        "is_markdown": True,
        "marker_style": "html",
    },
    "claude-code": {
        "filename": "CLAUDE.md",
        "is_markdown": True,
        "marker_style": "html",
    },
}


def inject_project_context(
    project_root: Path,
    context_content: str,
    tool_names: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Inject project context into tool-specific instruction files.
    
    Args:
        project_root: Absolute path to git repository root
        context_content: The context block to inject
        tool_names: List of tools to inject for (None = all). 
                    E.g., ["copilot", "cursor"]
    
    Returns:
        {tool_name: (success=True | error_message)}
    """
    if tool_names is None:
        tool_names = list(TOOL_TARGETS.keys())
    
    results = {}
    for tool_name in tool_names:
        if tool_name not in TOOL_TARGETS:
            results[tool_name] = f"Unknown tool: {tool_name}"
            continue
        
        config = TOOL_TARGETS[tool_name]
        file_path = project_root / config["filename"]
        
        try:
            _inject_into_file(
                file_path,
                context_content,
                is_markdown=config["is_markdown"],
            )
            results[tool_name] = True
        except Exception as e:
            results[tool_name] = f"ERROR: {e}"
    
    return results


def _inject_into_file(file_path: Path, content: str, is_markdown: bool = True) -> None:
    """Insert or replace the context block in a file using markers.
    
    Args:
        file_path: Path to the instruction file
        content: The context block to inject
        is_markdown: True for .md files, False for .rules files
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing content if file exists
    existing = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    
    # Create the wrapped block
    block = _wrap_content(content, is_markdown)
    
    # Replace or append
    if MARKER_START in existing and MARKER_END in existing:
        # Replace existing block
        updated = re.sub(
            rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
            block,
            existing,
            flags=re.DOTALL,
            count=1,
        )
    else:
        # Append new block
        separator = "\n\n" if existing and not existing.endswith("\n") else ""
        updated = existing + separator + block + "\n"
    
    file_path.write_text(updated, encoding="utf-8")


def _wrap_content(content: str, is_markdown: bool) -> str:
    """Wrap content with markers (HTML comments for both .md and .rules files).
    
    Args:
        content: The content to wrap
        is_markdown: True for markdown files, False for rules files
    
    Returns:
        Wrapped content with markers
    """
    wrapped = f"{MARKER_START}\n{content}\n{MARKER_END}"
    return wrapped


def remove_project_context(project_root: Path) -> bool:
    """Remove keel project context blocks from all tool files in a project.
    
    Args:
        project_root: Absolute path to git repository root
    
    Returns:
        True if successful, False if there were errors
    """
    all_success = True
    
    for tool_name, config in TOOL_TARGETS.items():
        file_path = project_root / config["filename"]
        if not file_path.exists():
            continue
        
        try:
            content = file_path.read_text(encoding="utf-8")
            
            if MARKER_START in content and MARKER_END in content:
                # Remove the block and surrounding whitespace
                updated = re.sub(
                    rf"\n?{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\n?",
                    "\n",
                    content,
                    flags=re.DOTALL,
                    count=1,
                )
                # Clean up multiple newlines
                updated = re.sub(r"\n\n\n+", "\n\n", updated).rstrip() + "\n"
                file_path.write_text(updated, encoding="utf-8")
        except Exception as e:
            print(f"Error removing context from {file_path}: {e}")
            all_success = False
    
    return all_success


def get_injected_files(project_root: Path) -> List[str]:
    """List which tool files have keel context injected.
    
    Args:
        project_root: Absolute path to git repository root
    
    Returns:
        List of tool names that have injected context
    """
    injected = []
    
    for tool_name, config in TOOL_TARGETS.items():
        file_path = project_root / config["filename"]
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
                if MARKER_START in content and MARKER_END in content:
                    injected.append(tool_name)
            except Exception:
                pass
    
    return injected
