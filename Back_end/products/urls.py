from django.urls import path
from .views import *

urlpatterns = [
    path("categories/", CategoryDetailsView.as_view(), name="category-list-create"),
    path("categories/<int:pk>/", CategoryDetailsView.as_view(), name="category-detail"),

    path("product/", ProductDetailsView.as_view(), name="product-list-create"),
    path("product/<int:pk>/", ProductDetailsView.as_view(), name="product-detail"),

    path("productlist/", ProductListAPIView.as_view(), name="Product-List"),
    path("productlist/<int:id>/", ProductListAPIView.as_view(), name="Product-List"),

    path("categorylist/", CategoryListAPIView.as_view(), name="Category-List"),
    path("categorylist/<int:id>/", CategoryListAPIView.as_view(), name="Category-List"),

    path("productfilter/<int:category_id>/", ProductFilter.as_view(), name="Product-Fillter"),

    path("orderdetails/", OrderDetailsView.as_view(), name="order-list-create"),
    path("orderdetails/<int:pk>/", OrderDetailsView.as_view(), name="order-detail"),

    path("orderspdf/<int:order_id>/", InvoicePDFView.as_view(), name="order-invoice-pdf"),

    path("order-status/<int:id>/", OrderStatusUpdateView.as_view(), name="order-status-update"),

    path("contactus/", ContactusView.as_view(), name="Contactus-View"),
    path("contactus/<int:pk>/", ContactusView.as_view(), name="Contactus-View"),

    path('offers/', OfferDetailsView.as_view(), name='offer-detail'),
    path('offers/<int:pk>/', OfferDetailsView.as_view(), name='offer-detail'),

    path('offers/category/<int:category_id>/', ProductsByCategory.as_view(), name='offers-by-category'),
]
