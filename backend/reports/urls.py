from django.urls import path

from . import views

urlpatterns = [
    path('session/', views.session, name='api-session'),
    path('auth/register/', views.register, name='api-register'),
    path('auth/login/', views.sign_in, name='api-login'),
    path('auth/logout/', views.sign_out, name='api-logout'),
    path('reports/', views.reports, name='api-reports'),
    path('claims/', views.my_claims, name='api-my-claims'),
    path('claims/create/', views.create_claim, name='api-create-claim'),
    path('attachments/upload/', views.upload_attachment, name='api-upload-attachment'),
]
