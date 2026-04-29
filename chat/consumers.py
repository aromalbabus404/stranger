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

        # Remove from queue if waiting
        if self.in_queue and self in waiting_users:
            waiting_users.remove(self)
        self.in_queue = False

        # Notify partner if connected
        if self.partner:
            await self.partner.send(text_data=json.dumps({
                "type": "partner_disconnected"
            }))
            # FIX: Also reset partner's in_queue so they can re-queue freely
            self.partner.in_queue = False
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

        # Prevent duplicate queue entry
        if self.in_queue:
            return

        # FIX: Skip stale disconnected users sitting in the queue
        partner = None
        while waiting_users:
            candidate = waiting_users.pop(0)
            # Skip ourselves
            if candidate is self:
                continue
            partner = candidate
            break

        if partner:
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
        # Notify old partner they were skipped
        if self.partner:
            await self.partner.send(text_data=json.dumps({
                "type": "partner_disconnected"
            }))
            # FIX: Reset old partner's state so they can re-queue after being skipped
            self.partner.in_queue = False
            self.partner.partner = None
            self.partner = None

        # FIX: Explicitly reset own in_queue before re-queuing.
        # Without this, the duplicate-queue guard in find_partner() would
        # block us from finding the next stranger after a skip.
        self.in_queue = False

        await self.find_partner()
