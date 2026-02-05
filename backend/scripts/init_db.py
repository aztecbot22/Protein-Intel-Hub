from app.db.base import Base
from app.db.session import engine
from app.models.annotation import Annotation
from app.models.user import User


def init():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init()
