from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # V1 API - OpenRouteService (Cloud-based)
    path('api/v1/route/', include('apps.routing.urls')),

    # V2 API - OSRM (Self-hosted)
    path('api/v2/route/', include('apps.routing.urls_v2')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
