from django.urls import path

from . import views

urlpatterns = [
    path('meetings/', views.meetings, name='meetings'),
    path('meetings/<int:pk>/', views.MeetingView.as_view(), name='meeting'),
    path('meetings/<int:meeting_id>/recordings/', views.RecordingUploadView.as_view(), name='upload_recording'),
    path('meetings/samples/<str:filename>', views.download_sample, name='download_sample'),
    path('meetings/<int:meeting_id>/recordings/<int:recording_id>/download', views.RecordingDownloadView.as_view(), name='download_recording'),
    path('meetings/<int:meeting_id>/recordings/<int:recording_id>/', views.RecordingView.as_view(), name='recording'),
    path('meetings/<int:meeting_id>/recordings/<int:recording_id>/tasks/<str:task_id>/', views.RecordingTaskView.as_view(), name='recording_task'),
]
