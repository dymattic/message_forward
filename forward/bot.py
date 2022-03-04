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
from pprint import pprint
from typing import Optional, Union

from maubot import Plugin, MessageEvent
from maubot.handlers import command, event
from mautrix.types import RoomID, EventType, MessageType

from .db import Database

try:
    import langdetect
    from langdetect.lang_detect_exception import LangDetectException
except ImportError:
    langdetect = None
    LangDetectException = None


class TranslateBotError(Exception):
    pass


class ForwardBot(Plugin):
    db: Database

    async def start(self) -> None:
        await super().start()
        self.db = Database(self.database)

    async def subscribe(self, evt: MessageEvent, fwd_room_id:
    Optional[str]) -> None:
        # if not await self.can_manage(evt):
        #    self.log.warn("-------------")
        #    return
        room_id = self.db.get_forward_by_room(evt.room_id)
        if not fwd_room_id:
            return
        else:
            fwd_room_id = RoomID(fwd_room_id)

        if not room_id:
            self.db.create_forward(room_id=evt.room_id, user_id=evt.sender, fwd_room_id=fwd_room_id)
        else:
            self.db.update_forward(room_id=evt.room_id, user_id=evt.sender, fwd_room_id=fwd_room_id)
        await self.show_subscriptions(evt=evt)

    async def unsubscribe(self, evt: MessageEvent) -> None:
        room_id = self.db.get_forward_by_room(evt.room_id)
        if room_id:
            self.db.remove_forward(room_id=evt.room_id)
        await self.show_subscriptions(evt=evt)

    def subscriptions(self, evt: MessageEvent) -> Union[str, None]:
        forward_config = self.db.get_forward_by_room(evt.room_id)
        if forward_config:
            return (
                f"Messages are forwarded from _[{RoomID(forward_config.room_id)}]_ -> _[{RoomID(forward_config.fwd_room_id)}] in this room.")
        else:
            return f"No messages in this room are forwarded."

    async def show_subscriptions(self, evt: MessageEvent) -> None:
        await evt.reply(self.subscriptions(evt))

    @event.on(EventType.ROOM_MESSAGE)
    async def event_handler(self, evt: MessageEvent) -> None:
        if (
                evt.content.msgtype == MessageType.NOTICE
                or evt.sender == self.client.mxid
                or evt.content.body[0:4] == '!fwd'
        ):
            self.log.info('Event handler Message content: %s', pprint(evt.content.body))
            return

        # get atc_config from db if existent ( database config = higher prio )
        forward_config = self.db.get_forward_by_room(evt.room_id)
        if forward_config:
            fwd_room_id = forward_config.fwd_room_id

        else:
            return

        await MessageEvent.client.send_message_event(room_id=fwd_room_id, event_type=evt.type, content=evt.content)

    @command.new("forward", aliases=["fwd"])
    @command.argument("fwd_command", required=False)
    @command.argument("fwd_room_id", pass_raw=True, required=False)
    async def command_handler(self, evt: MessageEvent, fwd_command: str,
                              fwd_room_id: RoomID) -> None:
        help_response = """__Usage:__ !fwd  <subcommand> [...]
- create <RoomID> - Automatically forward messages to specified room.
- remove - Stop forwarding messages from this room.
- show - Show forward settings for this room.

"""
        if fwd_command == 'create' and not fwd_room_id:
            await evt.reply("Usage: !forward create <RoomID>")
            return
        if fwd_command == 'create' and fwd_room_id:
            await self.subscribe(evt=evt, fwd_room_id=fwd_room_id)
            return
        if fwd_command == 'remove':
            await self.unsubscribe(evt=evt)
            return
        if fwd_command == 'show':
            await self.show_subscriptions(evt=evt)
            return
        if not fwd_room_id and fwd_command == 'help':
            await evt.reply(help_response + self.subscriptions(evt))
            return
        return
