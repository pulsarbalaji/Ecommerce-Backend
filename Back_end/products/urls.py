from django.urls import path
from .views import *

urlpatterns = [
    path("categories/", CategoryDetailsView.as_view(), name="category-list-create"),
    path("categories/<int:pk>/", CategoryDetailsView.as_view(), name="category-detail"),

    path("product/", ProductDetailsView.as_view(), name="product-list-create"),
    path("product/<int:pk>/", ProductDetailsView.as_view(), name="product-detail"),

    path("orderdetails/", OrderDetailsView.as_view(), name="order-list-create"),
    path("orderdetails/<int:pk>/", OrderDetailsView.as_view(), name="order-detail"),

     path("orderspdf/<int:order_id>/", InvoicePDFView.as_view(), name="order-invoice-pdf"),
]
