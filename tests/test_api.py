import pytest
from app.models.store import Store, Camera
from app.models.session import VisitorSession
from app.models.event import VisitorEvent

def test_health_check_endpoint(client):
    """
    Asserts health endpoint evaluates online state of active systems.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data["services"]
    assert "redis" in data["services"]

def test_events_ingestion_validation_and_caching(client, db_session):
    """
    Asserts validation parameters and registers raw vision streams events.
    """
    # 1. Seed store and tracking session meta
    store = Store(name="Test Purplle Branch", location="Mumbai")
    db_session.add(store)
    db_session.commit()
    
    camera = Camera(store_id=store.id, name="Test Front CCTV", rtsp_url="rtsp://test/1")
    db_session.add(camera)
    db_session.commit()
    
    session = VisitorSession(store_id=store.id, visitor_track_id="TRK-9009")
    db_session.add(session)
    db_session.commit()
    
    # 2. Post structured event
    event_payload = {
        "session_id": session.id,
        "camera_id": camera.id,
        "zone_name": "skincare_zone",
        "event_type": "ENTER",
        "duration": 0.0,
        "metadata": {"bbox": [100, 200, 150, 450]}
    }
    
    response = client.post("/api/v1/events", json=event_payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["zone_name"] == "skincare_zone"
    assert res_data["event_type"] == "ENTER"
    assert "id" in res_data

def test_events_ingestion_fails_on_missing_session(client):
    """
    Asserts that ingesting an event with an invalid session ID results in a 404.
    """
    event_payload = {
        "session_id": "non-existent-uuid",
        "camera_id": "non-existent-uuid",
        "zone_name": "makeup_zone",
        "event_type": "ENTER"
    }
    response = client.post("/api/v1/events", json=event_payload)
    assert response.status_code == 404

def test_metrics_analytical_aggregations(client, db_session):
    """
    Asserts metrics retrieval outputs values for store segments.
    """
    store = Store(name="Test Purplle Branch", location="Delhi")
    db_session.add(store)
    db_session.commit()
    
    response = client.get("/api/v1/metrics", params={"store_id": store.id})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "zone_name" in data[0]
    assert "total_footfall" in data[0]

def test_conversion_funnel_generation(client, db_session):
    """
    Asserts progression values inside marketing funnel chains.
    """
    store = Store(name="Test Purplle Branch", location="Delhi")
    db_session.add(store)
    db_session.commit()
    
    response = client.get("/api/v1/funnels", params={"store_id": store.id})
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == store.id
    assert "steps" in data
    assert len(data["steps"]) == 4
    assert data["steps"][0]["zone_name"] == "store_entrance"

def test_spatial_heatmaps_endpoints(client, db_session):
    """
    Asserts coordinate points mapping density are correctly fetched.
    """
    store = Store(name="Test Purplle Branch", location="Delhi")
    db_session.add(store)
    db_session.commit()
    
    response = client.get("/api/v1/heatmaps", params={"store_id": store.id})
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == store.id
    assert "points" in data
    assert len(data["points"]) > 0
    assert "x" in data["points"][0]
    assert "y" in data["points"][0]

def test_anomalies_alerts_retrieval(client, db_session):
    """
    Asserts warnings list can be retrieved for security audits.
    """
    store = Store(name="Test Purplle Branch", location="Delhi")
    db_session.add(store)
    db_session.commit()
    
    response = client.get("/api/v1/anomalies", params={"store_id": store.id})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "anomaly_type" in data[0]
    assert "severity" in data[0]
