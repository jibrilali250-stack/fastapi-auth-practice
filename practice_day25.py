from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
# Remove this line:
# from passlib.context import CryptContext
# Add these lines:
import hashlib
import jwt
from jwt import PyJWTError as JWTError
# 1. Configuration
SECRET_KEY = "my-super-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Remove the pwd_context line entirely!

def verify_password(plain_password, hashlib_password):
    # Hash the incoming password using SHA256
    password_bytes = plain_password.encode('utf-8')
    hashlib_bytes = hashlib.sha256(password_bytes).hexdigest()
    # Compare it to the hash in our fake database
    return hashlib_bytes == hashlib_password

fake_users_db = {
    "alice": {
        "username": "alice",
        "hashlib_password": "a71a7c7011f53a1bab3642ec2ce12593f05230ace8de1e3e7645f69efac1443d"
}
}
# 4. Pydantic Models
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str

# 5. Helper Functions
def verify_password(plain_password, hashlib_password):
    # 1. Convert the plain text password to bytes
    password_bytes = plain_password.encode('utf-8')
    
    # 2. Hash it using SHA256
    hashlib_bytes = hashlib.sha256(password_bytes).hexdigest()
    
    # 3. Compare it to the hash in the database
    return hashlib_bytes == hashlib_password
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # Create the JWT token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 6. OAuth2 Scheme (This tells Swagger to show a Login popup)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 7. Dependency: Get the current user from the token
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the token using our secret key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Check if user exists in DB
    user = fake_users_db.get(username)
    if user is None:
        raise credentials_exception
    return User(username=user["username"])

# 8. App & Routes
app = FastAPI()

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    # Check if user exists
    user = fake_users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashlib_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # If valid, generate a token
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user