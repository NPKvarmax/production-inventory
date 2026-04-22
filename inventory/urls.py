from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/<str:item_type>/', views.dashboard, name='dashboard'),
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('export/', views.export_inventory_csv, name='export_csv'),
]