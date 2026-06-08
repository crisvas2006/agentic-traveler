import pytest
from agentic_traveler.tools.db_client import get_db

@pytest.mark.integration
def test_metrics_views_syntax_and_accessibility():
    """
    Integration tests to ensure that the canonical SQL views for metrics
    are valid and accessible by the service role.
    """
    db = get_db()
    
    views_to_check = [
        "vw_growth_funnel_30d",
        "vw_saga_dropoff",
        "vw_data_growth_per_user",
        "vw_errors_24h",
        "vw_capacity_today",
        "vw_cost_per_user_30d"
    ]
    
    for view in views_to_check:
        try:
            # Query one row to verify syntax and existence without dumping large datasets
            response = db.table(view).select("*").limit(1).execute()
            assert response.data is not None
        except Exception as e:
            pytest.fail(f"Failed to query view {view}: {e}")

@pytest.mark.integration
def test_analytics_events_accessibility():
    db = get_db()
    try:
        response = db.table("analytics_events").select("id").limit(1).execute()
        assert response.data is not None
    except Exception as e:
        pytest.fail(f"Failed to query analytics_events: {e}")

@pytest.mark.integration
def test_metrics_daily_accessibility():
    db = get_db()
    try:
        response = db.table("metrics_daily").select("day").limit(1).execute()
        assert response.data is not None
    except Exception as e:
        pytest.fail(f"Failed to query metrics_daily: {e}")
