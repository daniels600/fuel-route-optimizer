from django.urls import path
from .views_v2 import OptimizeRouteV2View, HealthCheckV2View

urlpatterns = [
    path('optimize/', OptimizeRouteV2View.as_view(), name='optimize-route-v2'),
    path('health/', HealthCheckV2View.as_view(), name='health-check-v2'),
]
