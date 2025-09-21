from django.urls import path
from .views import (LoginView,SetNewPasswordView,AdminDetailsView,ForgotPasswordView,CustomerListView)

urlpatterns = [
    path("adminlogin/", LoginView.as_view(), name="login"),

    path("adminsdetails/", AdminDetailsView.as_view(), name="admin-list-create"),
    path("adminsdetails/<int:pk>/", AdminDetailsView.as_view(), name="admin-detail"),

    path("set-password/", SetNewPasswordView.as_view(), name="set-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),

    path("customerslist/", CustomerListView.as_view(), name="customer-list"),
    path("customerslist/<int:pk>/", CustomerListView.as_view(), name="customer-detail"),

]
