# payments/models.py
from django.db import models
from auth_model.models import CustomerDetails

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

    class meta:
        db_table ="payment_details"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.order_id} - {self.status}"

