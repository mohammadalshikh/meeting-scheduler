from dataclasses import dataclass
from datetime import datetime


@dataclass
class Room:
    id: int | None
    name: str
    capacity: int
    location: str | None = None
    description: str | None = None
    active: bool = True
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None

        return cls(
            id=row["id"],
            name=row["name"],
            capacity=row["capacity"],
            location=row.get("location"),
            description=row.get("description"),
            active=bool(row["active"]),
            created_at=row.get("created_at"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "capacity": self.capacity,
            "location": self.location,
            "description": self.description,
            "active": self.active,
            "created_at": self.created_at,
        }
