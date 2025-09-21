from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.shortcuts import get_object_or_404
from .models import *
from rest_framework.permissions import AllowAny
from django.conf import settings

from .serializers import *

class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Fetch Admin details
            try:
                details = user.details
                admin_data = {
                    "user_id":details.id,
                    "full_name": details.full_name,
                    "role": details.role,
                    "phone": details.phone,
                }
            except AdminDetails.DoesNotExist:
                admin_data = {}

            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "admin": admin_data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SetNewPasswordView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        password = request.data.get("password")

        try:
            uid = urlsafe_base64_decode(uid).decode()
            user = Auth.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Auth.DoesNotExist):
            return Response({"status": False, "message": "Invalid UID"}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"status": False, "message": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save()

        return Response({"status": True, "message": "Password set successfully"}, status=status.HTTP_200_OK)

class AdminDetailsView(APIView):
    # Create Admin
    def post(self, request):
        email = request.data.get("email")
        full_name = request.data.get("full_name")
        phone = request.data.get("phone")
        role = request.data.get("role")

        if not email:
            return Response({
                "status": False,
                "message": "Email is required",
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create Auth user
        user = Auth.objects.create_user(email=email, password="temp1234")

        # Create AdminDetails
        admin = AdminDetails.objects.create(
            auth=user,
            full_name=full_name,
            phone=phone,
            role=role
        )

        serializer = AdminDetailsSerializer(admin)

        # Send password reset email
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        send_mail(
            subject="Set Your Password",
            message=f"Hi {full_name},\n\nPlease set your password using the link below:\n{reset_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False
        )

        return Response({
            "status": True,
            "message": "Admin added successfully. Password setup email sent.",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    # List or Retrieve Admin
    def get(self, request, pk=None):
        if pk:
            admin = get_object_or_404(AdminDetails, pk=pk)
            serializer = AdminDetailsSerializer(admin)
        else:
            admins = AdminDetails.objects.all()
            serializer = AdminDetailsSerializer(admins, many=True)

        return Response({
            "status": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # Update Admin
    def put(self, request, pk=None):
        admin = get_object_or_404(AdminDetails, pk=pk)
        serializer = AdminDetailsSerializer(admin, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": True,
                "message": "Admin updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "status": False,
            "message": "Failed to update admin",
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    # Delete Admin
    def delete(self, request, pk):
        admin = get_object_or_404(AdminDetails, pk=pk)
        admin.auth.delete()  # Deletes both Auth and AdminDetails via OneToOne
        return Response({
            "status": True,
            "message": "Admin deleted successfully."
        }, status=status.HTTP_200_OK)

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"status": False, "message": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = Auth.objects.get(email=email)
        except Auth.DoesNotExist:
            return Response(
                {"status": False, "message": "User with this email does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generate reset link
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        # Send email
        send_mail(
            subject="Password Reset Request",
            message=f"Hi,\n\nClick the link below to reset your password:\n{reset_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response(
            {"status": True, "message": "Password reset email sent successfully"},
            status=status.HTTP_200_OK
        )
    

class CustomerListView(APIView):
    """
    API for getting all customers or a single customer by ID
    """

    def get(self, request, pk=None):
        if pk:
            # Get single customer by ID
            customer = get_object_or_404(CustomerDetails, pk=pk)
            serializer = CustomerSerializer(customer)
            return Response({
                "status": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        customers = CustomerDetails.objects.all().order_by("-created_at")
        serializer = CustomerSerializer(customers, many=True)
        return Response({
            "status": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)