from django.urls import path
from .views import CreateOrderAPIView, VerifyPaymentAPIView

urlpatterns = [
    path("orders/", CreateOrderAPIView.as_view(), name="create-order"),
    path("verify-payment/", VerifyPaymentAPIView.as_view(), name="verify-payment"),
]
