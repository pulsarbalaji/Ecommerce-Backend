from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid
from datetime import datetime, timedelta

class AuthManager(BaseUserManager):
    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError("User must provide either an email or phone")

        # Prevent duplicates
        extra_fields.pop("email", None)
        extra_fields.pop("phone", None)

        user = self.model(
            email=self.normalize_email(email) if email else None,
            phone=phone,
            **extra_fields
        )

        # ✅ hash password properly
        if password:
            user.set_password(password)   # uses make_password internally
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email=email, password=password, **extra_fields)


class Auth(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    login_method = models.CharField(
        max_length=20,
        choices=[
            ("email", "Email/Password"),
            ("phone", "Phone/OTP"),
            ("google", "Google"),
        ],
        default="email"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = AuthManager()

    def __str__(self):
        return self.email if self.email else self.phone  


class AdminDetails(models.Model):

    auth = models.OneToOneField(Auth, on_delete=models.CASCADE, related_name="details")
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=50, default="admin")

    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class meta:
        db_table ="admin_details"


class CustomerDetails(models.Model):
    auth = models.OneToOneField(Auth, on_delete=models.CASCADE, related_name="customer_details")

    full_name = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    profile_image = models.ImageField(upload_to="customers/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_details"

    def __str__(self):
        return f"Customer: {self.full_name}"

class EmailOTP(models.Model):
    email = models.EmailField()
    password = models.CharField(max_length=255,null=True)
    otp = models.CharField(max_length=6)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)
    
    class Meta:
        db_table = "email_otp_details"

    def __str__(self):
        return f"{self.email} - {self.otp}"
    

class PhoneOTP(models.Model):
    phone = models.CharField(max_length=15)
    otp = models.CharField(max_length=6)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        db_table = "phone_otp_details"

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)