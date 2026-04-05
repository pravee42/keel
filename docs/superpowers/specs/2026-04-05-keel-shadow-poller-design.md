# Design Spec: Keel Shadow Poller & Intelligence Expansion

**Date:** 2026-04-05  
**Topic:** Autonomous Shadow Clone, Multimodal Learning, and Project Management  
**Status:** Approved (via Brainstorming)

## 1. Overview
Keel's **Shadow Poller** enables the "memory clone" to act autonomously on behalf of the developer across Slack, GitHub, and Microsoft Teams. This update expands Keel's intelligence to include **Meeting Analysis**, **Prompting Style Learning**, **Gemini CLI capture**, and a **Dynamic Project Management Dashboard** with strict **Data Isolation**.

## 2. Key Goals
- **Autonomous Implementation:** Fix code issues and answer questions across platforms.
- **Developer Identity (Clone):** Respond using the developer's own accounts with their specific prompting style.
- **Multimodal Memory:** Learn from meetings (transcripts/audio) to capture decisions discussed verbally.
- **Full Capture Coverage:** Ensure Gemini CLI input/output is captured.
- **Project Mastery & Management:** Dynamically manage active projects via a dashboard with strict siloing of confidential project data.
- **Data Isolation:** Ensure core confidential info from "Project A" never leaks into "Project B."

## 3. Architecture Extensions

### A. Polling & Execution Engine (Shadow Clone)
- **Service:** Background agent (macOS LaunchAgent) running every 60s.
- **State:** Tracks `last_poll_timestamp` in `~/.keel/polling_state.json`.
- **Identity:** Uses developer tokens (Slack User Token, GitHub PAT) to act as a "Shadow Clone."

### B. Project Management & Isolation
- **Dashboard (`webserver.py`):** 
  - **Project List:** View all active/archived projects.
  - **Dynamic Management:** Toggle tracking, archive projects, and set project-specific sensitivity levels.
  - **Stats:** View decision counts and sync status per project.
- **Strict Siloing Logic (`analyzer.py` / `profile.py`):**
  - **Project-Bound Memory:** When generating a response for "Project A," Keel *only* reads decisions tagged with that project ID.
  - **Global Principles:** Only generic engineering principles (e.g., "Always use TDD") are shared cross-project.
  - **Confidentiality Tagging:** Users can mark specific decisions as `confidential`, which forces them into a local-only, project-exclusive memory block.

### C. Intelligence Modules
- **Style Learner (`style.py`):** Analyzes the *way* the developer prompts (verbosity, technical level, specific jargon).
- **Meeting Analyzer (`meeting.py`):** Extracts decisions and action items from transcripts/audio.
- **Gemini CLI Capture:** Shell function wrapper for `gemini` command to capture I/O.

## 4. Components & Files
- `poller.py`: Main background service for platform polling.
- `webserver.py`: Flask-based dashboard for project management.
- `meeting.py`: Module for processing meeting artifacts.
- `style.py`: Module for learning and replicating prompting styles.
- `shadow_agent.py`: High-certainty filtering and persona alignment logic.
- `projects.py`: Updated logic for project isolation and metadata management.

## 5. Security & Safety
- **Isolation Verification:** Automated check to ensure "Project B" never sees the text of "Project A" decisions.
- **High-Certainty Only:** Keel ignores any task where it is < 100% sure of the developer's intent or style.
- **Local-First Data:** All confidential project data stays in `~/.keel/` and is never sent to a generic cloud pool.

## 6. Testing Strategy
- **Isolation Test:** Attempt to generate a response for Project B and verify that no Project A context is leaked in the LLM prompt.
- **Dashboard CRUD Test:** Verify that adding/removing/archiving projects via the UI correctly updates `decisions.db` and sync status.
- **Gemini Capture Validation:** Verify that `gemini "question"` correctly appends to `queue.jsonl`.
