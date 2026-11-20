from fastapi.testclient import TestClient
from practice_day26 import app, create_db_and_tables
import uuid

# Create a test client
client = TestClient(app)

# Ensure the database tables exist for testing
create_db_and_tables()

def test_register_and_login():
    # Generate a random username so we don't get "User already exists" errors
    random_name = f"testuser_{uuid.uuid4().hex[:6]}"
    
    # 1. Test Registration
    response = client.post("/register", json={
        "username": random_name,
        "password": "supersecretpassword"
    })
    assert response.status_code == 200
    assert "created successfully" in response.json()["message"]

    # 2. Test Login (Get Token)
    login_response = client.post("/token", data={
        "username": random_name,
        "password": "supersecretpassword"
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # 3. Test Protected Route (Using the Token)
    headers = {"Authorization": f"Bearer {token}"}
    me_response = client.get("/users/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == random_name

    # 4. Test Protected Route WITHOUT Token (Should Fail)
    fail_response = client.get("/users/me")
    assert fail_response.status_code == 401