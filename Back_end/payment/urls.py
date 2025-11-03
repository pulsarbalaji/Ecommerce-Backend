from django.urls import path
from .views import (CreateOrderAPIView, CreateRazorpayOrderAPIView,VerifyPaymentAndCreateOrderAPIView,OrderTrackingAPIView,CustomerOrderHistoryView
                    ,GSTSettingView,CourierChargeSettingView)

urlpatterns = [
    path("orders/", CreateOrderAPIView.as_view(), name="create-order"),

    path("create-razorpay-order/", CreateRazorpayOrderAPIView.as_view(), name="create_razorpay_order"),
    path("verify-payment/", VerifyPaymentAndCreateOrderAPIView.as_view(), name="verify_payment_create_order"),

    path("order-tracking/<str:order_number>/", OrderTrackingAPIView.as_view(), name="order-tracking"),

    path("orders-history/<int:customer_id>/", CustomerOrderHistoryView.as_view(), name="customer-order-history"),

    path('settings/gst/', GSTSettingView.as_view(), name="gst-setting"),
    path('settings/courier-charge/', CourierChargeSettingView.as_view(), name="courier-charge-setting"),
]
