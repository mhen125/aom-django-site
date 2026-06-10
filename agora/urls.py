from django.urls import path

from . import views

app_name = "agora"

urlpatterns = [
    path("", views.agora_room, name="room"),
    path("api/messages/", views.api_messages, name="api_messages"),
    path("api/messages/post/", views.api_post_message, name="api_post_message"),
]
