from django.urls import path
from .views import CreateOrderAPIView, VerifyPaymentAPIView,OrderTrackingAPIView,CustomerOrderHistoryView

urlpatterns = [
    path("orders/", CreateOrderAPIView.as_view(), name="create-order"),
    path("verify-payment/", VerifyPaymentAPIView.as_view(), name="verify-payment"),

    path("order-tracking/<str:order_number>/", OrderTrackingAPIView.as_view(), name="order-tracking"),

    path("orders-history/<int:customer_id>/", CustomerOrderHistoryView.as_view(), name="customer-order-history"),
]
