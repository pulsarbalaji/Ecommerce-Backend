# payments/models.py
from django.db import models
from auth_model.models import CustomerDetails
from products.models import OrderDetails
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# models.py (payments part)

class Payment(models.Model):
    customer = models.ForeignKey(CustomerDetails, on_delete=models.CASCADE, related_name="payments")
    order = models.ForeignKey(OrderDetails, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")

    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, default="online")  # "online" / "cod"
    status = models.CharField(max_length=20, default="created") # created/success/failed/refunded

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_details"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer} - {self.amount} ({self.status})"


class GSTSetting(models.Model):
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table ="gst_details"

    def __str__(self):
        return f"GST: {self.gst_percentage}%"
    
class CourierChargeSetting(models.Model):
    courier_charge = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table ="courier_charge_details"

    def __str__(self):
        return f"Courier Charge: {self.courier_charge}"
    
@receiver(post_migrate)
def create_default_settings(sender, **kwargs):
    if sender.name == "payment":  
        GSTSetting.objects.get_or_create(id=1)
        CourierChargeSetting.objects.get_or_create(id=1)