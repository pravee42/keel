# Keel Shadow Poller & Intelligence Expansion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Keel's Shadow Poller, Project Management Dashboard, Meeting Analyzer, Style Learner, and Gemini CLI Capture.

**Architecture:** We are creating a background polling engine (`poller.py`) with platform-specific adapters to shadow the developer. We are also introducing `style.py` for prompt style matching, `meeting.py` for parsing meeting artifacts, and extending `webserver.py` and `projects.py` for isolated, dynamic project management.

**Tech Stack:** Python 3.9+, SQLite, Flask (webserver).

---

## Chunk 1: Foundation and Gemini CLI Capture

### Task 1: Update `install.py` for Gemini CLI Capture

**Files:**
- Modify: `install.py`

- [ ] **Step 1: Write test (or reproduction script) for `install.py` modifications**

```python
# test_install.py
import install
def test_gemini_wrapper_generation():
    # Mock OS checks and verify gemini wrapper logic is output
    pass
```

- [ ] **Step 2: Update `install_shell_wrappers` in `install.py` to include Gemini CLI**

```python
    # Inside install.py
    # ...
    wrapper_content += """
# Gemini CLI Wrapper
gemini() {
    local cmd="gemini $@"
    local output
    output=$(command gemini "$@")
    local exit_code=$?
    
    # Send to keel queue
    local payload="COMMIT: $cmd\nCHANGED FILES:\n$output"
    echo "$payload" | python3 ~/.keel/queue_writer.py --source gemini --type prompt --cwd "$(pwd)"
    
    echo "$output"
    return $exit_code
}
"""
```

- [ ] **Step 3: Run the test to ensure wrapper script logic is sound.**

- [ ] **Step 4: Commit**
```bash
git add install.py
git commit -m "feat: add gemini cli shell wrapper capture"
```

## Chunk 2: Intelligence Modules (Style & Meeting)

### Task 2: Create Prompt Style Learner (`style.py`)

**Files:**
- Create: `style.py`
- Test: `test_style.py`

- [ ] **Step 1: Write the failing test**
```python
# test_style.py
import style
from store import Decision

def test_analyze_style():
    decisions = [Decision(id="1", timestamp="", domain="code", title="", context="", options="", choice="", reasoning="I prefer to use standard libs. No bloat.", principles="[]", outcome="", tags="[]", paths="[]", project="")]
    style_profile = style.analyze_prompting_style(decisions)
    assert "concise" in style_profile.lower() or "direct" in style_profile.lower()
```

- [ ] **Step 2: Write minimal implementation for `style.py`**
```python
# style.py
import llm
from store import Decision

def analyze_prompting_style(decisions: list[Decision]) -> str:
    """Analyze the developer's written reasoning to extract stylistic traits."""
    if not decisions:
        return "Standard professional tone."
    
    samples = "\n".join([d.reasoning for d in decisions[:20]])
    prompt = f"""Analyze the following text written by a developer and describe their style (verbosity, technical jargon, formatting). Return a concise 2-3 sentence style guide.
    
    Samples:
    {samples}
    """
    return llm.complete([{"role": "user", "content": prompt}], max_tokens=256)
```

- [ ] **Step 3: Run test to verify it passes**
`pytest test_style.py`

- [ ] **Step 4: Commit**
```bash
git add style.py test_style.py
git commit -m "feat: implement prompt style analysis module"
```

### Task 3: Create Meeting Analyzer (`meeting.py`)

**Files:**
- Create: `meeting.py`
- Test: `test_meeting.py`

- [ ] **Step 1: Write the failing test**
```python
# test_meeting.py
import meeting

def test_extract_meeting_decisions():
    transcript = "Alice: Let's use Postgres instead of MySQL because we need JSONB support. Bob: Agreed."
    decisions = meeting.extract_decisions_from_transcript(transcript)
    assert len(decisions) == 1
    assert "Postgres" in decisions[0]["choice"]
```

- [ ] **Step 2: Write minimal implementation for `meeting.py`**
```python
# meeting.py
import json
import llm

def extract_decisions_from_transcript(transcript_text: str) -> list[dict]:
    prompt = f"""Extract architectural or strategic decisions from this meeting transcript.
    Return ONLY a JSON array of objects with keys: title, context, options, choice, reasoning.
    
    Transcript:
    {transcript_text}
    """
    text = llm.complete([{"role": "user", "content": prompt}], max_tokens=1024)
    start, end = text.find("["), text.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    return json.loads(text[start:end])
```

- [ ] **Step 3: Run test to verify it passes**
`pytest test_meeting.py`

- [ ] **Step 4: Commit**
```bash
git add meeting.py test_meeting.py
git commit -m "feat: implement meeting transcript decision extraction"
```

## Chunk 3: Project Management Dashboard Isolation

### Task 4: Extend `projects.py` for Confidentiality & UI Toggles

**Files:**
- Modify: `projects.py`

- [ ] **Step 1: Write the failing test**
```python
# test_projects.py
import projects

def test_project_metadata_management():
    projects.set_project_metadata("/test/proj", archived=True, confidential=True)
    meta = projects.get_project_metadata("/test/proj")
    assert meta["archived"] is True
    assert meta["confidential"] is True
```

- [ ] **Step 2: Write minimal implementation in `projects.py`**
(Implementation involves reading/writing to `~/.keel/projects/` metadata JSON files, ensuring `archived` and `confidential` flags are respected during sync).

- [ ] **Step 3: Run test to verify it passes**
`pytest test_projects.py`

- [ ] **Step 4: Commit**
```bash
git add projects.py test_projects.py
git commit -m "feat: add confidentiality and archival support to projects"
```

### Task 5: Expose Project Management in `webserver.py`

**Files:**
- Modify: `webserver.py`
- Modify/Create: `templates/projects.html`

- [ ] **Step 1: Add endpoints for `/projects` to list and toggle states.**
- [ ] **Step 2: Update HTML templates to render the project list with toggle buttons.**
- [ ] **Step 3: Verify the UI routes load correctly without error.**
- [ ] **Step 4: Commit**
```bash
git add webserver.py templates/
git commit -m "feat: add project management dashboard UI"
```

## Chunk 4: Shadow Poller and Execution

### Task 6: Implement `shadow_agent.py`

**Files:**
- Create: `shadow_agent.py`
- Test: `test_shadow_agent.py`

- [ ] **Step 1: Write the failing test**
```python
# test_shadow_agent.py
import shadow_agent

def test_high_certainty_filter():
    # Mocking llm response to return confidence 100
    response = shadow_agent.analyze_mention("Hey, how do we handle auth?", "persona text")
    assert response["confidence"] == 100
```

- [ ] **Step 2: Write minimal implementation for `shadow_agent.py`**
```python
# shadow_agent.py
import json
import llm

def analyze_mention(message: str, persona_context: str) -> dict:
    prompt = f"""You are a shadow clone of the developer. Analyze this mention.
    Persona: {persona_context}
    Message: {message}
    
    Can you answer this with 100% certainty based ONLY on the persona?
    Return JSON: {{"confidence": 0-100, "action": "reply|code|ignore", "response_text": "..."}}
    """
    text = llm.complete([{"role": "user", "content": prompt}], max_tokens=512)
    # Parse JSON...
    # (Implementation omitted for brevity in plan, but expected to parse and return dict)
    pass
```

- [ ] **Step 3: Run test to verify it passes**
`pytest test_shadow_agent.py`

- [ ] **Step 4: Commit**
```bash
git add shadow_agent.py test_shadow_agent.py
git commit -m "feat: implement high-certainty shadow agent filter"
```

### Task 7: Implement Background `poller.py`

**Files:**
- Create: `poller.py`
- Create: `adapters/__init__.py`, `adapters/github.py`, `adapters/slack.py`

- [ ] **Step 1: Write a basic scaffolding test for the poller loop.**
- [ ] **Step 2: Implement `poller.py` with a main loop that runs every 60s, checks adapters, filters via `shadow_agent.py`, and dispatches responses.**
- [ ] **Step 3: Verify execution logic.**
- [ ] **Step 4: Commit**
```bash
git add poller.py adapters/
git commit -m "feat: implement shadow polling background service"
```

---
