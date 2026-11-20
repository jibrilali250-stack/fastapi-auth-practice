from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from sqlalchemy.orm import selectinload
from typing import Annotated

# 1. Define the Team Model
class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    headquarters: str
    
    # This tells SQLModel: "A Team has a list of Heroes"
    heroes: list["Hero"] = Relationship(back_populates="team")

# 2. Define the Hero Model
class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    secret_name: str
    age: int | None = Field(default=None, index=True)
    
    # This is the Foreign Key! It links this hero to a Team's ID.
    team_id: int | None = Field(default=None, foreign_key="team.id")
    
    # This tells SQLModel: "A Hero belongs to a Team"
    team: Team | None = Relationship(back_populates="heroes")

# 3. Database Setup (Same as yesterday)
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# 4. Endpoint: Create a Team
@app.post("/teams/")
def create_team(team: Team, session: SessionDep):
    session.add(team)
    session.commit()
    session.refresh(team)
    return team

# 5. Endpoint: Create a Hero (and assign them to a team!)
@app.post("/heroes/")
def create_hero(hero: Hero, session: SessionDep):
    session.add(hero)
    session.commit()
    session.refresh(hero)
    return hero

# 6. Endpoint: Get a Team and see all its Heroes!
@app.get("/teams/{team_id}")
def read_team(team_id: int, session: SessionDep):
    # 1. Get the team
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # 2. Manually query the database for all heroes with this team_id
    statement = select(Hero).where(Hero.team_id == team_id)
    team_heroes = session.exec(statement).all()
    
    # 3. Return a dictionary and explicitly include the heroes
    return {
        "id": team.id,
        "name": team.name,
        "headquarters": team.headquarters,
        "heroes": team_heroes 
    }