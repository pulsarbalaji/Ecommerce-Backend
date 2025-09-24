from django.urls import path
from .views import (LoginView,SetNewPasswordView,AdminDetailsView,ForgotPasswordView,CustomerListView,
GoogleRegisterView,GoogleLoginView,EmailRegisterStep1,EmailRegisterStep2,CustomerEmailAPIView,CustomerDetailsAPIView,
PhoneRegisterStep1,PhoneRegisterStep2,PhoneLoginStep1,PhoneLoginStep2)

urlpatterns = [
    path("adminlogin/", LoginView.as_view(), name="login"),

    path("adminsdetails/", AdminDetailsView.as_view(), name="admin-list-create"),
    path("adminsdetails/<int:pk>/", AdminDetailsView.as_view(), name="admin-detail"),

    path("set-password/", SetNewPasswordView.as_view(), name="set-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),

    path("customerslist/", CustomerListView.as_view(), name="customer-list"),
    path("customerslist/<int:pk>/", CustomerListView.as_view(), name="customer-detail"),

    path("google/", GoogleRegisterView.as_view(), name="google-register"),
    path("google/login/", GoogleLoginView.as_view(), name="google-login"),

    path("register/email-step1/", EmailRegisterStep1.as_view(),name="Email-register"),
    path("register/email-step2/", EmailRegisterStep2.as_view(),name="Email-register"),

    path("customer/login/", CustomerEmailAPIView.as_view(),name="Customer-Email-Login"),

    path("customerdetails/", CustomerDetailsAPIView.as_view(),name="Customer-Details"),
    path("customerdetails/<int:pk>/", CustomerDetailsAPIView.as_view(),name="Customer-Details"),

    path("phone-register-step1/", PhoneRegisterStep1.as_view(), name="phone-register-step1"),
    path("phone-register-step2/", PhoneRegisterStep2.as_view(), name="phone-register-step2"),

    path("phone-login-step1/", PhoneLoginStep1.as_view(), name="phone-login-step1"),
    path("phone-login-step2/", PhoneLoginStep2.as_view(), name="phone-login-step2"),

]
