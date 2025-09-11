from django.urls import path

from . import views

urlpatterns = [
    path('rooms/', views.rooms, name='rooms'),
    path('rooms/<int:pk>/', views.RoomView.as_view(), name='room'),
]
