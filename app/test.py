# from app.security import get_password_hash
# print(get_password_hash("password"))

import datetime
import logging

from requests import session


now = datetime.utcnow()
logging.debug(f"Current UTC time: {now}, Session start: {session.start_time}, end: {session.end_time}")