import store
import json
import os
from pathlib import Path

def test_requirements_and_links():
    # Setup test DB
    store.DB_PATH = Path("test_decisions.db")
    if store.DB_PATH.exists():
        store.DB_PATH.unlink()
        
    r = store.Requirement(
        id=store.new_id(), timestamp="2026-04-09", text="Must be fast",
        type="Functional", priority="High", project="proj1", source_event_id="e1"
    )
    store.save_requirement(r)
    
    d = store.Decision(
        id=store.new_id(), timestamp="2026-04-09", domain="code", title="Use cache",
        context="Slow DB", options="Memcached, Redis", choice="Redis", reasoning="Familiarity",
        principles="[]", outcome="", tags="[]", paths="[]", project="proj1",
        is_implicit=1, alternatives=json.dumps(["Memcached", "Local"])
    )
    store.save(d)
    store.link_requirement_decision(r.id, d.id, "fulfills")
    
    reqs = store.get_requirements()
    assert len(reqs) == 1
    assert reqs[0].text == "Must be fast"
    
    impl_decisions = store.get_implicit_decisions()
    assert len(impl_decisions) == 1
    assert impl_decisions[0].title == "Use cache"
    
    store.accept_implicit_decision(d.id)
    assert len(store.get_implicit_decisions()) == 0
    
    links = store.get_decision_requirements(d.id)
    assert len(links) == 1
    assert links[0] == r.id
    
    if store.DB_PATH.exists():
        store.DB_PATH.unlink()
    print("Tests passed")

if __name__ == "__main__":
    test_requirements_and_links()
