# payments/models.py
from django.db import models
from auth_model.models import CustomerDetails
from django.db.models.signals import post_migrate
from django.dispatch import receiver
class Payment(models.Model):
    customer = models.ForeignKey(CustomerDetails, on_delete=models.CASCADE)

    order_id = models.CharField(max_length=100)  # Razorpay order ID
    payment_id = models.CharField(max_length=100, blank=True, null=True)  # Razorpay payment ID
    amount = models.FloatField()
    currency = models.CharField(max_length=10, default="INR")
    status = models.CharField(max_length=50, default="created") 
    method = models.CharField(max_length=20, default="online")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table ="payment_details"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.order_id} - {self.status}"

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