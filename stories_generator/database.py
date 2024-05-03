from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from telegram_assinaturas_bot.config import config

db = create_engine(config['DATABASE_URI'])
Session = sessionmaker(db)
