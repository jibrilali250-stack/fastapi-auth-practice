from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Field, Session, SQLModel, create_engine, select

# 1. Define the Database Table (Model)
class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    secret_name: str
    age: int | None = Field(default=None, index=True)

# 2. Set up the Database
# This creates a file called "database.db" in your folder
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# check_same_thread=False is required for SQLite in FastAPI
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

# 3. Create the Tables
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# 4. Create a Database Session Dependency
def get_session():
    with Session(engine) as session:
        yield session

# This tells FastAPI to pass a database session into any endpoint that asks for it
SessionDep = Annotated[Session, Depends(get_session)]

# 5. Start the App
app = FastAPI()

# Run the table creation when the app starts
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# 6. Endpoint: Create a Hero (Save to DB)
@app.post("/heroes/")
def create_hero(hero: Hero, session: SessionDep) -> Hero:
    session.add(hero)
    session.commit()
    session.refresh(hero) # This updates the hero with the new ID from the database
    return hero

# 7. Endpoint: Read all Heroes (Read from DB)
@app.get("/heroes/")
def read_heroes(session: SessionDep) -> list[Hero]:
    heroes = session.exec(select(Hero)).all()
    return heroes

# 8. Endpoint: Read a single Hero by ID
@app.get("/heroes/{hero_id}")
def read_hero(hero_id: int, session: SessionDep):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero