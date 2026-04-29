from django.shortcuts import render
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

def index(request):
    # Count online users from channel layer (approximate)
    return render(request, 'chat/index.html')

def chat_room(request):
    return render(request, 'chat/room.html')
