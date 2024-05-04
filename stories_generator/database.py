from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from stories_generator.config import config

db = create_engine(config['DATABASE_URI'])
Session = sessionmaker(db)
