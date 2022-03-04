# forward - A maubot plugin to forward messages from one room to another.
# Copyright (C) 2022 Dmitrij Pastian
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import NamedTuple, Optional

from mautrix.types import UserID, RoomID
from sqlalchemy import (Column, String, Integer, Table, MetaData,
                        select, and_)
from sqlalchemy.engine.base import Engine

Forward = NamedTuple("Forward", room_id=RoomID, user_id=UserID, fwd_room_id=RoomID)


class Database:
    db: Engine
    forward: Table
    version: Table

    def __init__(self, db: Engine) -> None:
        self.db = db
        metadata = MetaData()
        self.forward = Table("forward", metadata,
                             Column("room_id", String(255), primary_key=True),
                             Column("user_id", String(255), nullable=False),
                             Column("fwd_room_id", String(255), nullable=True)
                             )
        self.version = Table("version", metadata,
                             Column("version", Integer, primary_key=True))
        self.upgrade()

    def upgrade(self) -> None:
        self.db.execute("CREATE TABLE IF NOT EXISTS version (version INTEGER PRIMARY KEY)")
        try:
            version, = next(self.db.execute(select([self.version.c.version])))
        except (StopIteration, IndexError):
            version = 0
        if version == 0:
            self.db.execute("""CREATE TABLE IF NOT EXISTS forward (
                room_id VARCHAR(255) NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                fwd_room_id VARCHAR(255) NULL
            )""")
            version = 1
        self.db.execute(self.version.delete())
        self.db.execute(self.version.insert().values(version=version))

    def get_forward_by_room(self, room_id: RoomID) -> Optional[Forward]:
        rows = self.db.execute(select([self.forward]).where(self.forward.c.room_id == room_id))
        try:
            row = next(rows)
            return Forward(*row)
        except (ValueError, StopIteration):
            return None

    def update_room_id(self, old: RoomID, new: RoomID) -> None:
        self.db.execute(self.forward.update()
                        .where(self.forward.c.room_id == old)
                        .values(room_id=new))

    def create_forward(self, room_id: RoomID, user_id: UserID, fwd_room_id: RoomID) -> bool:
        res = self.db.execute(self.forward.insert().values(room_id=room_id, user_id=user_id, fwd_room_id=fwd_room_id))
        return True

    def update_forward(self, room_id: RoomID, user_id: UserID, fwd_room_id: RoomID) -> None:
        tbl = self.forward
        self.db.execute(tbl.update()
                        .where(tbl.c.room_id == room_id)
                        .values(user_id=user_id, fwd_room_id=fwd_room_id))

    def remove_forward(self, room_id: RoomID) -> None:
        tbl = self.forward
        self.db.execute(tbl.delete().where(and_(tbl.c.room_id == room_id)))
