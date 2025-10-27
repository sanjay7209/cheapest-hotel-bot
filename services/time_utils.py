from datetime import datetime
import pytz
NY_TZ = pytz.timezone("America/New_York")

def today_ny_iso():
    return datetime.now(NY_TZ).date().isoformat()
