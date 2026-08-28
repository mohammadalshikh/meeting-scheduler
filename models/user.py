from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: int | None
    username: str
    email: str
    password_hash: str
    role: str
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None

        return cls(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=row["role"],
            created_at=row.get("created_at"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "role": self.role,
            "created_at": self.created_at,
        }
