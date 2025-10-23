from rest_framework import serializers
from .models import Auth,AdminDetails,CustomerDetails,EmailOTP,PhoneOTP
from django.contrib.auth.hashers import check_password
import random
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            user = Auth.objects.get(email=data['email'])
        except Auth.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        if not check_password(data['password'], user.password):
            raise serializers.ValidationError("Invalid email or password")
        
        if not user.is_staff:
            raise serializers.ValidationError("You are not authorized to access this section")

        data['user'] = user
        return data


class AdminDetailsSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='auth.email', read_only=True)
    class Meta:
        model = AdminDetails  
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerDetails
        fields = "__all__"

class AuthSerializer(serializers.ModelSerializer):
    customer_details = CustomerSerializer(read_only=True)

    class Meta:
        model = Auth
        fields = ["id", "email", "phone", "login_method", "customer_details"]

class EmailRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)

    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]

        # Check if already exists
        if Auth.objects.filter(email=email).exists():
            raise serializers.ValidationError("Email already registered")

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Store email + password in OTP table
        otp_entry = EmailOTP.objects.create(
            email=email,
            password=password,  # raw for now (NOT hashed)
            otp=otp,
        )

        # Send OTP
        send_mail(
            subject="Your Ecommerce Registration OTP",
            message=f"Your OTP is {otp}. It will expire in 5 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )

        return otp_entry


class VerifyEmailOTPSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    otp = serializers.CharField()

    def validate(self, data):
        try:
            otp_obj = EmailOTP.objects.get(session_id=data["session_id"])
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid session")

        if otp_obj.is_expired():
            raise serializers.ValidationError("OTP expired")

        if otp_obj.otp != data["otp"]:
            raise serializers.ValidationError("Invalid OTP")

        data["otp_obj"] = otp_obj
        return data

    def create(self, validated_data):
        otp_obj = validated_data["otp_obj"]

        # Create Auth user properly
        user = Auth.objects.create(
            email=otp_obj.email,
            login_method="email",
            is_active=True,  # ✅ activate after verification
        )
        user.set_password(otp_obj.password)  # hash password here
        user.save()

        otp_obj.delete()  # cleanup

        return user


class PhoneOTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneOTP
        fields = ['phone']

    def validate_phone(self, value):
        # ✅ Check if phone already exists in Auth table
        if Auth.objects.filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value

    def create(self, validated_data):
        phone = validated_data['phone']
        otp = str(random.randint(100000, 999999))

        # Optional: remove old OTPs for same phone
        PhoneOTP.objects.filter(phone=phone).delete()

        otp_entry = PhoneOTP.objects.create(phone=phone, otp=otp)
        return otp_entry

class VerifyPhoneOTPSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    otp = serializers.CharField()

    def validate(self, data):
        try:
            otp_obj = PhoneOTP.objects.get(session_id=data["session_id"])
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid session")
        if otp_obj.is_expired():
            raise serializers.ValidationError("OTP expired")
        if otp_obj.otp != data["otp"]:
            raise serializers.ValidationError("Invalid OTP")
        data["otp_obj"] = otp_obj
        return data

    def create(self, validated_data):
        otp_obj = validated_data["otp_obj"]
        phone = otp_obj.phone

        user, created = Auth.objects.get_or_create(phone=phone, defaults={"login_method": "phone", "is_active": True})
        otp_obj.is_verified = True
        otp_obj.save()

        # JWT tokens
        refresh = RefreshToken.for_user(user)
        return {
            "user": user,
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }
    
class PhoneLoginOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=10)

    def create(self, validated_data):
        phone = validated_data["phone"]

        # Check if user exists
        try:
            user = Auth.objects.get(phone=phone)
        except Auth.DoesNotExist:
            raise serializers.ValidationError({"error":"Phone number not registered"})

        # Generate OTP
        otp = str(random.randint(100000, 999999))
        otp_entry = PhoneOTP.objects.create(phone=phone, otp=otp)

        return otp_entry


class VerifyPhoneLoginOTPSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    otp = serializers.CharField()

    def validate(self, data):
        try:
            otp_obj = PhoneOTP.objects.get(session_id=data["session_id"])
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid session")

        if otp_obj.is_expired():
            raise serializers.ValidationError("OTP expired")

        if otp_obj.otp != data["otp"]:
            raise serializers.ValidationError("Invalid OTP")

        data["otp_obj"] = otp_obj
        return data

    def create(self, validated_data):
        otp_obj = validated_data["otp_obj"]
        phone = otp_obj.phone

        user = Auth.objects.get(phone=phone)
        otp_obj.is_verified = True
        otp_obj.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return {
            "user": user,
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }