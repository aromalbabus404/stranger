from channels.generic.websocket import AsyncWebsocketConsumer
import json

waiting_users = []

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()

        global waiting_users

        print("User connected")

        if waiting_users:
            partner = waiting_users.pop(0)

            self.room_name = f"room_{id(self)}_{id(partner)}"
            partner.room_name = self.room_name

            await self.channel_layer.group_add(self.room_name, self.channel_name)
            await self.channel_layer.group_add(self.room_name, partner.channel_name)

            await self.channel_layer.group_send(
                self.room_name,
                {
                    "type": "chat_start",
                }
            )
        else:
            waiting_users.append(self)

            await self.send(text_data=json.dumps({
                "type": "waiting"
            }))

    async def chat_start(self, event):
        await self.send(text_data=json.dumps({
            "type": "connected"
        }))

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message")

        if hasattr(self, "room_name"):
            await self.channel_layer.group_send(
                self.room_name,
                {
                    "type": "chat_message",
                    "message": message
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": event["message"]
        }))

    async def disconnect(self, close_code):
        global waiting_users

        if self in waiting_users:
            waiting_users.remove(self)