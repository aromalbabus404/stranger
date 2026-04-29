from channels.generic.websocket import AsyncWebsocketConsumer
import json

waiting_users = []

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        self.partner = None
        self.in_queue = False

    async def disconnect(self, close_code):
        global waiting_users

        if self in waiting_users:
            waiting_users.remove(self)
        self.in_queue = False

        if self.partner:
            old_partner = self.partner
            self.partner = None
            old_partner.partner = None
            old_partner.in_queue = False
            try:
                await old_partner.send(text_data=json.dumps({
                    "type": "partner_disconnected"
                }))
            except Exception:
                pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get("type")

        if msg_type == "find_partner":
            await self.find_partner()

        elif msg_type == "skip":
            await self.skip_partner()

        elif msg_type == "chat_message":
            if self.partner:
                await self.partner.send(text_data=json.dumps({
                    "type": "chat_message",
                    "message": data.get("message")
                }))

        elif msg_type in ["offer", "answer", "ice_candidate"]:
            if self.partner:
                await self.partner.send(text_data=json.dumps(data))

        elif msg_type == "typing":
            if self.partner:
                await self.partner.send(text_data=json.dumps({"type": "typing"}))

        elif msg_type == "stop_typing":
            if self.partner:
                await self.partner.send(text_data=json.dumps({"type": "stop_typing"}))

    async def find_partner(self):
        global waiting_users

        # Already in queue — do nothing
        if self.in_queue:
            return

        # Already has a partner — do nothing
        if self.partner:
            return

        # Find a valid waiting user
        partner = None
        while waiting_users:
            candidate = waiting_users.pop(0)
            if candidate is self:
                continue
            partner = candidate
            break

        if partner:
            # Link the two users
            self.partner = partner
            partner.partner = self
            partner.in_queue = False
            self.in_queue = False

            await self.send(text_data=json.dumps({
                "type": "partner_found",
                "role": "caller"
            }))
            await partner.send(text_data=json.dumps({
                "type": "partner_found",
                "role": "receiver"
            }))

        else:
            waiting_users.append(self)
            self.in_queue = True
            await self.send(text_data=json.dumps({
                "type": "waiting"
            }))

    async def skip_partner(self):
        global waiting_users

        # Disconnect from current partner
        if self.partner:
            old_partner = self.partner
            self.partner = None
            old_partner.partner = None
            old_partner.in_queue = False

            try:
                await old_partner.send(text_data=json.dumps({
                    "type": "partner_disconnected"
                }))
            except Exception:
                pass

        # Reset own state before searching again
        self.in_queue = False
        self.partner = None

        await self.find_partner()
