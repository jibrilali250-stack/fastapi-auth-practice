import time
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader

app = FastAPI()

# 1. Define a simulated database of valid API keys
VALID_API_KEYS = {
    "secret-key-123": "Alice",
    "secret-key-456": "Bob"
}

# 2. Set up the Security Scheme for Swagger UI
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

# 3. Create the Dependency function
async def verify_api_key(api_key: str = Security(api_key_header)):
    # Notice how everything below here is indented!
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing"
        )
        
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
        
    # Whatever you return here gets passed into the endpoint
    return VALID_API_KEYS[api_key]

async def admin_only(user: Annotated[str, Depends(verify_api_key)]):
    if user != "Alice":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# 4. Use the Dependency
@app.get("/protected-data")
async def get_protected_data(user: Annotated[str, Depends(verify_api_key)]):
    return {
        "message": f"Hello {user}! You are seeing top secret data.",
        "data": ["secret1", "secret2", "secret3"]
    }

# 5. A public endpoint

# ... your existing /protected-data and /public endpoints ...

# --- ADD THIS NEW ENDPOINT AT THE BOTTOM ---
@app.get("/admin-panel")
async def admin_panel(admin_user: Annotated[str, Depends(admin_only)]):
    return {
        "message": f"Welcome to the admin panel, {admin_user}!",
        "status": "You have superuser access."
    }
@app.get("/public")
async def get_public_data():
    return {"message": "This is public. Anyone can see it."}