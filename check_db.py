from app.database import SessionLocal
s = SessionLocal()
print(s.execute(__import__('sqlalchemy').text("SELECT 1")).scalar())
s.close()