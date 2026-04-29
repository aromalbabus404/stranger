from django.shortcuts import render

def index(request):
    return render(request, 'chat/index.html')

def chat_room(request):
    return render(request, 'chat/room.html')