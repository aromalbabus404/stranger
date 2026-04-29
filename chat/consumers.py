from channels.generic.websocket import AsyncWebsocketConsumer
import json

waiting_users = []

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        self.partner = None
        self.in_queue = False
        print("User connected")

    async def disconnect(self, close_code):
        global waiting_users

        if self.in_queue and self in waiting_users:
            waiting_users.remove(self)

        if self.partner:
            await self.partner.send(text_data=json.dumps({
                "type": "partner_disconnected"
            }))
            self.partner.partner = None
            self.partner = None

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

    # =========================
    async def find_partner(self):
        global waiting_users

        # prevent duplicate queue
        if self.in_queue:
            return

        if waiting_users:
            partner = waiting_users.pop(0)

            self.partner = partner
            partner.partner = self

            self.in_queue = False
            partner.in_queue = False

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

    # =========================
    async def skip_partner(self):
        if self.partner:
            await self.partner.send(text_data=json.dumps({
                "type": "partner_disconnected"
            }))
            self.partner.partner = None
            self.partner = None

        await self.find_partner()