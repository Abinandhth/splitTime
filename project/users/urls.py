from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('',views.main,name='main'),
    path('login/',views.login,name='login'),
    path('home/',views.home,name='home'),
    path('signup/',views.signup,name='signup'),
    path('logout/',views.logout,name='logout'),
    path('pdf_delete/<int:pk>/',views.pdf_delete,name='pdf_delete'),
    path('section_complete/<int:slot_id>/',views.section_complete,name='section_complete'),
    path('account_guide/',views.account_guide,name='account_guide'),
    path('stay_motivated_guide/',views.stay_motivated_guide,name='stay_motivated_guide'),
     # Password reset views
    path("reset_password/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("reset_password_sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset_password_complete/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
