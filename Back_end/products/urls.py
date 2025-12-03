from django.urls import path
from .views import *

urlpatterns = [
    path("categories/", CategoryDetailsView.as_view(), name="category-list-create"),
    path("categories/<int:pk>/", CategoryDetailsView.as_view(), name="category-detail"),

    path("product/", ProductDetailsView.as_view(), name="product-list-create"),
    path("product/<int:pk>/", ProductDetailsView.as_view(), name="product-detail"),

    path("productlist/", ProductListAPIView.as_view(), name="Product-List"),
    path("productlist/<int:id>/", ProductListAPIView.as_view(), name="Product-List"),
    path("stock/", StockAvailability.as_view(), name="stock"),

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

    path('Dashboard/', DashboardAPIView.as_view(), name='offer-detail'),

    path("favorites/toggle/", FavoriteToggleView.as_view(), name="favorite-toggle"),
    path("favorites/", FavoriteListView.as_view(), name="favorite-list"),
    path("favorites/ids/", FavoriteListIdsView.as_view(), name="favorite-list"),

    path("productvariant/", ProductVariant.as_view(), name="Product-Variant"),
    path("productvariant/<int:pk>/", ProductVariant.as_view(), name="Product-Variant"),
    path("productvariantfilter/", ProductVariantFillter.as_view(), name="Product-Variant"),
    path("mainproductlist/", MainProductDropdown.as_view(), name="MainProduct-Dropdown"),

    path("feedback/<int:product_id>/", ProductFeedbackAPIView.as_view(), name="product-feedback"),

    path("product-feedback-list/<int:product_id>/", ProductFeedbackListAPIView.as_view(), name="product-feedback-list"),
    path("product-rating-summary/<int:product_id>/", ProductRatingSummaryAPIView.as_view(),name="Product-Rating-Summary"),
    path("product-feedback-filter/<int:product_id>/", ProductFeedbackFilterAPIView.as_view(),name="ProductFeedback-filter"),
    path("admin-feedback-list/", AdminReviewListAPIView.as_view(),name ="admin-feedback-list"),
    path("admin-approval/<int:review_id>/", AdminReviewStatusAPIView.as_view(),name ="Admin-Review-Status"),
    path("admin-feedback/<int:review_id>/", AdminReviewDetailAPIView.as_view(),name ="Admin-Review-view"),
    path("admin-feedback-delete/<int:review_id>/", AdminReviewDeleteAPIView.as_view(),name ="Admin-Review-Delete"),


    path("orders/search/", GlobalOrderSearchView.as_view(), name="global-order-search"),
    path("products/search/", GlobalProductSearchView.as_view(), name="global-product-search"),

    path("customer-notifications/<int:customer_id>/", CustomerNotifications.as_view(), name="Customer-Notifications"),
    path("readnotifications/<int:id>/", MarkNotificationRead.as_view(), name="Mark-Notification-Read"),
    path("readnotifications/all/<int:customer_id>/", MarkAllNotificationsRead.as_view(),  name="Mark-All-Notifications"),
    path("notification/<int:id>/", DeleteNotification.as_view(),  name="Delete-Notification"),
    path("notifications/clear/<int:customer_id>/", ClearAllNotifications.as_view(),  name="Clear-All-Notifications"),

    path("checkout-initiate/", CheckoutInitiate.as_view(), name="Checkout-Initiate"),
    path("checkout-validate/", CheckoutValidate.as_view(), name="Checkout-Validate"),

    path("orders/print-address/", PrintAddressPDFView.as_view(), name="Print-Address-PDF"),
    path("single-orders/print-address/", PrintSingleAddressPDFView.as_view(), name="single-Print-Address-PDF"),
    path("orders/unprinted/", UnprintedOrdersView.as_view(), name="Unprinted-Orders"),



]
