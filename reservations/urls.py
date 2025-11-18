from django.urls import path

from . import views

urlpatterns = [
    path('reservations/', views.reservations, name='reservations'),
    path('reservations/<int:pk>/', views.ReservationView.as_view(), name='reservation'),
    path('reservations/schedules/<int:room_id>/', views.reservations_schedules, name='reservable_schedules'),
]
