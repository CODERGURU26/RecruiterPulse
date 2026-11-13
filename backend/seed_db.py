import sys
import os

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base, engine, SessionLocal
from app.services.workspace_bootstrap import ensure_default_workspace


def seed():
    print("Ensuring default workspace and taxonomy...", flush=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        ensure_default_workspace(db)
        db.commit()
        print("\nDatabase ready! Upload real recruiter spreadsheets to generate live reports.", flush=True)
        print("   No fake reports seeded; all data will come from your real files.\n", flush=True)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
