from django.db import models
from auth_model.models import AdminDetails,CustomerDetails
from django.utils.translation import gettext_lazy as _
import uuid

class Category(models.Model):
    category_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    category_image = models.ImageField(upload_to="category/", blank=True, null=True)

    created_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='category',null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "category_details"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Product(models.Model):
    product_name = models.CharField(max_length=300, blank=False, null=False)
    product_description = models.TextField(max_length=3000, blank=False, null=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")

    product_image = models.ImageField(upload_to="products/", blank=True, null=True)

    stock_quantity = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)

    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)

    created_by = models.ForeignKey(AdminDetails,on_delete=models.CASCADE, related_name='product',null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products_details"
        ordering = ["-created_at"]

    def __str__(self):
        return self.product_name

class OrderDetails(models.Model):

    class OrderStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSING = "processing", _("Processing")
        SHIPPED = "shipped", _("Shipped")
        DELIVERED = "delivered", _("Delivered")
        CANCELLED = "cancelled", _("Cancelled")
        RETURNED = "returned", _("Returned")
    
    class PaymentMethod(models.TextChoices):
        COD = "cod", _("Cash on Delivery")
        CARD = "card", _("Credit/Debit Card")
        UPI = "upi", _("UPI / Wallet")
        NET_BANKING = "netbanking", _("Net Banking")

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    customer = models.ForeignKey(CustomerDetails, on_delete=models.CASCADE,related_name="orders",)

    order_number = models.CharField(max_length=20, unique=True, editable=False)

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:10].upper()}"
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
        db_table = "invoice"
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
