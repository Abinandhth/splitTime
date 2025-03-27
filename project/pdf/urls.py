from django.urls import path
from . import views


urlpatterns = [
    path('sections/',views.sections,name='sections'),
    path('schedules/',views.schedules,name='schedules'),
    path('reschedule/<int:slot_id>/', views.reschedule_schedule, name='reschedule_schedule'),
    path('pdf_reschedule/<int:pk>/',views.pdf_reschedule,name='pdf_reschedule'),
    path('upload_pdf/<int:pk>/',views.upload_pdf,name='upload_pdf')
]
