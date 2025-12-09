from django.urls import path
from .views import (VerifyPaymentAndCreateOrderAPIView,OrderTrackingAPIView,CustomerOrderHistoryView
                    ,GSTSettingView,CourierChargeSettingView,ReserveOrderAPIView)

urlpatterns = [

    path("orders/reserve/", ReserveOrderAPIView.as_view(), name="Reserve-Order"),
    path("orders/verify/", VerifyPaymentAndCreateOrderAPIView.as_view(), name="Verify-Payment-And-Create-Orderr"),

    path("order-tracking/<str:order_number>/", OrderTrackingAPIView.as_view(), name="order-tracking"),

    path("orders-history/<int:customer_id>/", CustomerOrderHistoryView.as_view(), name="customer-order-history"),

    path('settings/gst/', GSTSettingView.as_view(), name="gst-setting"),
    path('settings/courier-charge/', CourierChargeSettingView.as_view(), name="courier-charge-setting"),
]
