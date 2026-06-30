from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def build_sessionmaker(database_url: str):
    engine = create_engine(database_url)
    return sessionmaker(bind=engine)
