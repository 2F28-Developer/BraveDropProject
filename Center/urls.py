from django.conf.urls.static import static
from django.contrib import admin
from django.conf import settings
from django.urls import re_path, path, include
from django.views.static import serve
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('oauth/', include('social_django.urls', namespace='social')),
    path('', include('main.urls', namespace='main')),
    path('profile/', include('main.urls', namespace='main')),
    path('favicon.ico', RedirectView.as_view(
        url=settings.STATIC_URL + 'favicon.ico', permanent=True
    )),
]

urlpatterns += [
    re_path(
        r'^media/(?P<path>.*)$',
        serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
