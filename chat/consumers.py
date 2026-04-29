import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer

# Store users with metadata
waiting_users = []   # [{'channel': channel_name, 'country': 'India'}]
active_pairs = {}    # channel_name -> partner_channel


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user_id = str(uuid.uuid4())[:8]
        self.partner = None
        self.country = None

        await self.accept()

        await self.send(json.dumps({
            'type': 'connected',
            'message': 'Connected to OmegaChat server',
            'user_id': self.user_id,
        }))

    async def disconnect(self, code):
        # Remove from waiting queue
        waiting_users[:] = [
            user for user in waiting_users
            if user['channel'] != self.channel_name
        ]

        # Handle active pair
        if self.channel_name in active_pairs:
            partner_channel = active_pairs.pop(self.channel_name, None)

            if partner_channel:
                active_pairs.pop(partner_channel, None)

                try:
                    await self.channel_layer.send(partner_channel, {
                        'type': 'partner_disconnected',
                    })
                except Exception:
                    pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'find_partner':
            country = data.get('country', 'India')  # default India
            mode = data.get('mode', 'text')

            self.country = country
            await self.find_partner(mode, country)

        elif msg_type == 'chat_message':
            await self.forward_to_partner({
                'type': 'chat_message',
                'message': data['message']
            })

        elif msg_type == 'skip':
            await self.skip_partner()

        # WebRTC signaling
        elif msg_type in ('offer', 'answer', 'ice_candidate'):
            await self.forward_to_partner(data)

        elif msg_type == 'typing':
            await self.forward_to_partner({'type': 'typing'})

        elif msg_type == 'stop_typing':
            await self.forward_to_partner({'type': 'stop_typing'})

    async def find_partner(self, mode, country):
        # Already paired
        if self.channel_name in active_pairs:
            return

        partner_channel = None

        # Find same-country user
        for user in waiting_users:
            if user['country'] == country and user['channel'] != self.channel_name:
                partner_channel = user['channel']
                waiting_users.remove(user)
                break

        if partner_channel:
            # Create pair
            active_pairs[self.channel_name] = partner_channel
            active_pairs[partner_channel] = self.channel_name

            # Notify self
            await self.send(json.dumps({
                'type': 'partner_found',
                'role': 'caller',
                'mode': mode,
            }))

            # Notify partner
            await self.channel_layer.send(partner_channel, {
                'type': 'partner_found_msg',
                'role': 'receiver',
                'mode': mode,
            })

        else:
            # Add to waiting list
            waiting_users.append({
                'channel': self.channel_name,
                'country': country
            })

            await self.send(json.dumps({
                'type': 'waiting',
                'message': f'Waiting for a stranger from {country}...',
            }))

    async def forward_to_partner(self, payload):
        if self.channel_name in active_pairs:
            partner_channel = active_pairs[self.channel_name]

            await self.channel_layer.send(partner_channel, {
                'type': 'forward_message',
                'payload': payload,
            })

    async def skip_partner(self):
        if self.channel_name in active_pairs:
            partner_channel = active_pairs.pop(self.channel_name, None)

            if partner_channel:
                active_pairs.pop(partner_channel, None)

                try:
                    await self.channel_layer.send(partner_channel, {
                        'type': 'partner_disconnected',
                    })
                except Exception:
                    pass

        # Reconnect (India default)
        await self.find_partner('video', self.country or 'India')

    # -------- Handlers -------- #

    async def partner_found_msg(self, event):
        await self.send(json.dumps({
            'type': 'partner_found',
            'role': event['role'],
            'mode': event['mode'],
        }))

    async def forward_message(self, event):
        await self.send(json.dumps(event['payload']))

    async def partner_disconnected(self, event):
        active_pairs.pop(self.channel_name, None)

        await self.send(json.dumps({
            'type': 'partner_disconnected',
            'message': 'Stranger has disconnected.',
        }))