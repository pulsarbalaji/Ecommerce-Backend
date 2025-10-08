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
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .models import *
from rest_framework.permissions import AllowAny
from django.conf import settings
import requests
from twilio.rest import Client
from google.oauth2 import id_token
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth


from .serializers import *

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase/firebase_credentials.json")
    firebase_admin.initialize_app(cred)

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
    

if not firebase_admin._apps:
    firebase_admin.initialize_app()

class GoogleRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        full_name = request.data.get("full_name")
        address = request.data.get("address")
        dob = request.data.get("dob")
        gender = request.data.get("gender")
        profile_image = request.data.get("profile_image")

        if not token:
            return Response({"error": "No token provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 🔑 Verify Firebase ID token
            decoded_token = firebase_auth.verify_id_token(token)
            email = decoded_token.get("email")

            if not email:
                return Response({"error": "Email not found in token"}, status=status.HTTP_400_BAD_REQUEST)

            # 🔑 Get or create Auth user
            user, created = Auth.objects.get_or_create(email=email, defaults={"login_method": "google"})

            # 🔑 If user is newly created, also create CustomerDetails
            if created:
                CustomerDetails.objects.create(
                    auth=user,
                    full_name=full_name if full_name else decoded_token.get("name", ""),
                    address=address,
                    dob=dob,
                    gender=gender,
                    profile_image=profile_image  # Only if you handle image upload properly
                )

            # 🔑 Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "login_method": user.login_method,
                    "customer": {
                        "full_name": user.customer_details.full_name if hasattr(user, "customer_details") else None,
                        "address": user.customer_details.address if hasattr(user, "customer_details") else None,
                        "dob": user.customer_details.dob if hasattr(user, "customer_details") else None,
                        "gender": user.customer_details.gender if hasattr(user, "customer_details") else None,
                        "profile_image": (
                            request.build_absolute_uri(user.customer_details.profile_image.url)
                            if hasattr(user, "customer_details") and user.customer_details.profile_image
                            else None
                        ),
                    },
                },
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({
                "message": "No token provided"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify Firebase ID token
            decoded_token = firebase_auth.verify_id_token(token)
            email = decoded_token.get("email")
            name = decoded_token.get("name")
            picture = decoded_token.get("picture")

            if not email:
                return Response({
                    "message": "Email not found in token"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get or create Auth user
            user, created = Auth.objects.get_or_create(
                email=email,
                defaults={"login_method": "google"}
            )

            # Ensure login method is google
            if user.login_method != "google":
                user.login_method = "google"
                user.save()

            # Create or update CustomerDetails
            customer, c_created = CustomerDetails.objects.get_or_create(auth=user)
            if c_created:
                customer.full_name = name or ""
                customer.profile_image = picture or None
                customer.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "phone": user.phone,
                    "login_method": user.login_method,
                    "customer_details": {
                        "id": customer.id,
                        "full_name": customer.full_name,
                        "address": customer.address,
                        "dob": customer.dob,
                        "gender": customer.gender,
                        "profile_image": (
                            customer.profile_image.url if customer.profile_image else picture
                        ),
                        "created_at": customer.created_at,
                        "updated_at": customer.updated_at,
                        "auth": customer.auth.id
                    }
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class EmailRegisterStep1(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailRegisterSerializer(data=request.data)
        if serializer.is_valid():
            otp_entry = serializer.save()
            return Response({
                "message": "OTP sent to your email",
                "session_id": otp_entry.session_id
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailRegisterStep2(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailOTPSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Create related customer details if not already exists
            if not hasattr(user, "customer_details"):
                CustomerDetails.objects.create(
                    auth=user,
                    full_name=user.email.split("@")[0].title()
                )

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            user_data = AuthSerializer(user).data  # same structure as login response

            return Response({
                "message": "Account created successfully",
                "user": user_data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomerEmailAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email, password=password)

        if user is None:
            return Response({"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"error": "This account is disabled"}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        user_data = AuthSerializer(user).data  

        return Response({
            "message": "Login successful",
            "user": user_data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_200_OK)


class CustomerDetailsAPIView(APIView):

    def post(self, request):
        auth_id = request.data.get("auth")
        if not auth_id:
            return Response({"error": "auth id is required"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CustomerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(auth_id=auth_id)
            return Response({"message": "Customer details created", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        try:
            customer = CustomerDetails.objects.get(pk=pk)
        except CustomerDetails.DoesNotExist:
            return Response({"error": "Customer details not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CustomerSerializer(customer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Customer details updated", "data": serializer.data}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PhoneRegisterStep1(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PhoneOTPSerializer(data=request.data)
        if serializer.is_valid():
            otp_entry = serializer.save()
            print(otp_entry.phone,"Test")

            # Send WhatsApp OTP via Twilio
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=f"{otp_entry.otp}is your Ecommerce Register verification code.",
                from_="whatsapp:+14155238886",  
                to=f"whatsapp:+91{otp_entry.phone}"
            )

            return Response({
                "message": "OTP sent via WhatsApp",
                "session_id": otp_entry.session_id
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PhoneRegisterStep2(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyPhoneOTPSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.save()
            return Response({
                "message": "Phone verified successfully",
                "user_id": data["user"].id,
                "phone": data["user"].phone,
                "access": data["access"],
                "refresh": data["refresh"]
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class PhoneLoginStep1(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PhoneLoginOTPSerializer(data=request.data)
        if serializer.is_valid():
            otp_entry = serializer.save()

            # Send OTP via Twilio WhatsApp
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=f"{otp_entry.otp}is your Ecommerce Register verification code.",
                from_="whatsapp:+14155238886",  # Twilio Sandbox
                to=f"whatsapp:+91{otp_entry.phone}"
            )

            return Response({
                "message": "OTP sent via WhatsApp",
                "session_id": otp_entry.session_id
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PhoneLoginStep2(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyPhoneLoginOTPSerializer(data=request.data)

        if serializer.is_valid():
            data = serializer.save()  # This should return {"user": user, "access": ..., "refresh": ...}
            user = data["user"]

            # Serialize user + customer details
            user_data = AuthSerializer(user).data  

            return Response({
                "message": "Login successful",
                "user": user_data,              
                "access": data["access"],
                "refresh": data["refresh"],
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):

    def post(self, request):
        # 1️⃣ Delete DRF token if it exists
        try:
            Token.objects.filter(user=request.user).delete()
        except Exception:
            pass  # no token exists, ignore

        # 2️⃣ Blacklist JWT refresh token if provided
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                return Response(
                    {"error": "Invalid refresh token"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 3️⃣ Logout successful
        return Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK,
        )