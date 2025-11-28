from django.urls import path
from .views import OptimizeRouteView, HealthCheckView

urlpatterns = [
    path('optimize/', OptimizeRouteView.as_view(), name='optimize-route'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]
