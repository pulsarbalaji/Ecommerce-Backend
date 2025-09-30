# payments/views.py
import razorpay
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import hmac, hashlib

from .models import Payment

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class CreateOrderView(APIView):
    def post(self, request):
        amount = request.data.get("amount")
        user = request.user

        data = {
            "amount": int(amount) * 100,  # paise
            "currency": "INR",
            "payment_capture": 1,
        }
        order = client.order.create(data=data)

        Payment.objects.create(
            user=user,
            order_id=order["id"],
            amount=amount,
            status=order["status"],
        )
        return Response(order)


class VerifyPaymentView(APIView):
    def post(self, request):
        data = request.data
        order_id = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature = data.get("razorpay_signature")

        generated_signature = hmac.new(
            bytes(settings.RAZORPAY_KEY_SECRET, "utf-8"),
            bytes(order_id + "|" + payment_id, "utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if generated_signature == signature:
            payment = Payment.objects.get(order_id=order_id)
            payment.payment_id = payment_id
            payment.status = "paid"
            payment.save()
            return Response({"status": "success"})
        else:
            return Response({"status": "failed"}, status=status.HTTP_400_BAD_REQUEST)
