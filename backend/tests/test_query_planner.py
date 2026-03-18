from app.services.discovery.query_planner import build_discovery_query_plan


def test_query_planner_generates_google_and_linkedin_queries():
    plan = build_discovery_query_plan(
        research_topics=["machine learning", "NLP", "machine learning"],
        preferences={
            "fields": ["information retrieval"],
            "universities": ["Stanford University"],
            "countries": ["USA"],
            "degree_targets": ["MS", "PhD"],
        },
    )

    assert plan["google_queries"]
    assert plan["linkedin_queries"]
    assert any("site:.edu" in q for q in plan["google_queries"])
    assert any("linkedin.com" in q for q in plan["linkedin_queries"])
    assert any('fully funded' in q.lower() for q in plan["google_queries"])
    assert any('scholarship' in q.lower() for q in plan["google_queries"])
    # Dedup expected
    assert "machine learning" in [k.lower() for k in plan["keywords"]]
    assert len(plan["keywords"]) == len(set(k.lower() for k in plan["keywords"]))


def test_query_planner_handles_empty_inputs():
    plan = build_discovery_query_plan(research_topics=[], preferences={})
    assert isinstance(plan["google_queries"], list)
    assert isinstance(plan["linkedin_queries"], list)
    assert isinstance(plan["keywords"], list)
