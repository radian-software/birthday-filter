from dataclasses import dataclass
import dotenv

dotenv.load_dotenv()

import os
from pathlib import Path


@dataclass
class Credentials:
    url: str
    username: str
    password: str


CALDAV = Credentials(
    url=os.environ["CALDAV_URL"],
    username=os.environ["CALDAV_USERNAME"],
    password=os.environ["CALDAV_PASSWORD"],
)

CARDDAV = Credentials(
    url=os.environ["CARDDAV_URL"],
    username=os.environ["CARDDAV_USERNAME"],
    password=os.environ["CARDDAV_PASSWORD"],
)


BIRTHDAY_CALENDAR_ID = os.environ["BIRTHDAY_CALENDAR_ID"]

DATA_DIR = Path(__file__).parent.parent / "data"
