from django.db import models
from auth_model.models import AdminDetails,CustomerDetails
from django.utils.translation import gettext_lazy as _
import uuid
from django.utils import timezone
from datetime import date
from django.db.models import Avg,Sum





class Category(models.Model):
    category_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    category_image = models.ImageField(upload_to="category/", blank=True, null=True)

    created_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='category',null=True,blank=True)
    updated_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='update_category',null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "category_details"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Product(models.Model):
    product_name = models.CharField(max_length=300, blank=False, null=False)
    product_description = models.TextField(max_length=3000, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)  # e.g. 100, 1, 500
    quantity_unit = models.CharField(max_length=20,blank=True, null=True)  # e.g. ml, L, g, kg, pcs

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="variants")

    product_image = models.ImageField(upload_to="products/", blank=True, null=True)

    stock_quantity = models.PositiveIntegerField(default=0)

    is_available = models.BooleanField(default=True)
    reserved_by = models.ForeignKey("auth_model.CustomerDetails",on_delete=models.SET_NULL,null=True,blank=True,related_name="reserved_products")
    reserved_until = models.DateTimeField(null=True, blank=True)


    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)

    created_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='product',null=True,blank=True)
    updated_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='update_product',null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products_details"
        ordering = ["-created_at"]

    def is_reserved(self):
        """Check if reservation is still active"""
        return self.reserved_until and self.reserved_until > timezone.now()

    def clear_reservation(self):
        """Release reservation when expired"""
        self.reserved_by = None
        self.reserved_until = None
        self.save()
    
    def clear_expired_reservations(self):
        ProductReservation.objects.filter(
            product=self,
            reserved_until__lt=timezone.now()
        ).delete()
    
    def available_stock(self, for_user=None):
    # Clear expired reservations
        self.clear_expired_reservations()

        # Total reserved by other users only
        qs = ProductReservation.objects.filter(
            product=self,
            reserved_until__gt=timezone.now(),
        )

        if for_user:
            qs = qs.exclude(user=for_user)

        reserved_by_others = qs.aggregate(total=Sum("quantity"))["total"] or 0

        return self.stock_quantity - reserved_by_others

    @property
    def clean_name(self):
        return self.product_name.replace("_", " ").title()
        
    def __str__(self):
        return self.product_name
    
    def is_variant(self):
        return self.parent is not None
    def save(self, *args, **kwargs):

        if self.stock_quantity <= 0:
            self.is_available = False
        else:
            self.is_available = True
        super().save(*args, **kwargs)

class OrderDetails(models.Model):

    class OrderStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        ORDER_CONFIRMED  = "order_confirmed", _("Order Confirmed")
        SHIPPED = "shipped", _("Shipped")
        DELIVERED = "delivered", _("Delivered")
        CANCELLED = "cancelled", _("Cancelled")
        RETURNED = "returned", _("Returned")
    
    class PaymentMethod(models.TextChoices):
        COD = "cod", _("Cash on Delivery")
        ONLINE = "online", _("Online")
        

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    customer = models.ForeignKey(CustomerDetails, on_delete=models.CASCADE,related_name="orders",)

    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)

    contact_number = models.CharField(max_length=10, blank=True, null=True)
    secondary_number = models.CharField(max_length=10, blank=True, null=True)

    order_number = models.CharField(max_length=20, unique=True, editable=False)

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    preferred_courier_service = models.CharField(max_length=300, blank=True, null=True)
    courier_number = models.CharField(max_length=100, blank=True, null=True) 

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)

    shipping_address = models.TextField(blank=False, null=False)
    billing_address = models.TextField(blank=True, null=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivered_at = models.DateTimeField(blank=True, null=True)

    ordered_at = models.DateTimeField(auto_now_add=True)

    is_printed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
    # Set delivered_at when status changes to delivered
        if self.pk:
            old = OrderDetails.objects.get(pk=self.pk)
            if old.status != self.status and self.status == self.OrderStatus.DELIVERED:
                self.delivered_at = timezone.now()
        else:
            if self.status == self.OrderStatus.DELIVERED:
                self.delivered_at = timezone.now()

        # Generate ORDER NUMBER (only first time)
        if not self.order_number:
            import random
            from datetime import datetime

            today = datetime.now().strftime("%Y%m%d")   # YYYYMMDD
            unique = False

            while not unique:
                random_part = str(random.randint(100000, 999999))  # 6-digit random
                generated = f"ORD-{today}-{random_part}"

                if not OrderDetails.objects.filter(order_number=generated).exists():
                    unique = True
                    self.order_number = generated

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_number} - {self.customer.full_name}"

    class Meta:
        db_table = "order_details"
        ordering = ["-created_at"]


class OrderItem(models.Model):
    order = models.ForeignKey(OrderDetails, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="order")
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total = self.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.Product_name} x {self.quantity}"
    
    class Meta:
        db_table = "order_items"

class Invoice(models.Model):
    order = models.OneToOneField("OrderDetails", on_delete=models.CASCADE, related_name="invoice")
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    generated_at = models.DateTimeField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice {self.invoice_number} for Order {self.order.order_number}"

    class Meta:
        db_table = "invoice_details"
        ordering = ["-generated_at"]

class Contactus(models.Model):
    name = models.CharField(max_length=300, blank=False, null=False)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15,null=True, blank=True)
    message = models.TextField(max_length=3000, blank=False, null=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contact_us"
        ordering = ["-created_at"]

class OfferDetails(models.Model):
    category = models.ForeignKey("Category", on_delete=models.CASCADE, related_name='offers')
    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name='offers')

    offer_name = models.CharField(max_length=300)
    offer_percentage = models.PositiveIntegerField(
    null=True,
    blank=True,
    help_text="Offer percentage (e.g., 10 for 10%)"
)
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(default=date.today)

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='offer',null=True,blank=True)
    updated_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='update_offer',null=True,blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'offer_details'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.offer_name} - {self.offer_percentage}%"

    # ✅ Automatically deactivate expired offers
    def check_and_update_status(self):
        today = timezone.now().date()
        if self.end_date < today and self.is_active:
            self.is_active = False
            self.save(update_fields=['is_active'])

class FavoriteProduct(models.Model):
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name="favorite_products")
    customer = models.ForeignKey(CustomerDetails,on_delete=models.CASCADE,related_name="favorite_products")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'favorite_details'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer} - {self.product}"
    
class ProductFeedback(models.Model):
    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name="feedbacks")
    user = models.ForeignKey("auth_model.CustomerDetails", on_delete=models.CASCADE, related_name="product_feedbacks")
    rating = models.PositiveSmallIntegerField(default=5)  
    comment = models.TextField(blank=True, null=True, max_length=200)
    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_feedback"
        unique_together = ("product", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.product_name} - {self.rating}⭐ by {self.user}"

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

        self.update_product_rating()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.update_product_rating()

    def update_product_rating(self):
        avg_rating = self.product.feedbacks.aggregate(avg=Avg("rating"))["avg"] or 0.0
        self.product.average_rating = round(avg_rating, 2)
        self.product.save(update_fields=["average_rating"])


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        ORDER_STATUS = "order_status", _("Order Status")
        PAYMENT = "payment", _("Payment")
        SYSTEM = "system", _("System")
        PRODUCT_RATING = "product_rating", _("Product Rating")

    # ONLY customer notifications
    customer = models.ForeignKey("auth_model.CustomerDetails",on_delete=models.CASCADE,related_name="notifications")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,related_name="notifications")

    order = models.ForeignKey("OrderDetails",on_delete=models.CASCADE,null=True,blank=True,related_name="notifications")

    type = models.CharField(max_length=50, choices=NotificationType.choices, default=NotificationType.ORDER_STATUS)

    title = models.CharField(max_length=255)  
    message = models.TextField()               

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_details"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.type})"

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])


class ProductReservation(models.Model):
    user = models.ForeignKey(CustomerDetails, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    reserved_until = models.DateTimeField()       # expires individually
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")     # one reservation per user-product
