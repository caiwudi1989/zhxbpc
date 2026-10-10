from datetime import datetime,timezone,timedelta
t=datetime(2026,1,1,tzinfo=timezone.utc)
print(t.astimezone(timezone(timedelta(hours=8))).isoformat())
