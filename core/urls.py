from django.urls import path
from . import views, api

urlpatterns = [
    path('auth/login', views.login_view),
    path('auth/me', views.me_view),
    path('auth/logout', views.logout_view),
    path('reports/overview', api.reports_overview),
    path('<str:resource>', api.resource_list),
    path('<str:resource>/<str:ident>', api.resource_item),
]
