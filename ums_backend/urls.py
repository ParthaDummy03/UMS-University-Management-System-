from django.conf import settings
from django.http import FileResponse
from django.urls import include, path, re_path
from django.views.static import serve


def home(request):
    return FileResponse(open(settings.BASE_DIR / 'index.html', 'rb'), content_type='text/html; charset=utf-8')


urlpatterns = [
    path('api/', include('core.urls')),
    path('', home),
    re_path(r'^(?P<path>(?:css|js|assets)/.*)$', serve, {'document_root': settings.BASE_DIR}),
]
