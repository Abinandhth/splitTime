from django.urls import path
from . import views

urlpatterns = [
    path('',views.main,name='main'),
    path('login/',views.login,name='login'),
    path('home/',views.home,name='home'),
    path('signup/',views.signup,name='signup'),
    path('logout/',views.logout,name='logout'),
    path('pdf_delete/<int:pk>/',views.pdf_delete,name='pdf_delete'),
]
