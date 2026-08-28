from dataclasses import dataclass
from datetime import datetime


@dataclass
class Reservation:
    id: int | None
    user_id: int
    room_id: int
    title: str
    start_time: datetime
    end_time: datetime
    status: str = "confirmed"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None

        return cls(
            id=row["id"],
            user_id=row["user_id"],
            room_id=row["room_id"],
            title=row["title"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            status=row["status"],
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "room_id": self.room_id,
            "title": self.title,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
