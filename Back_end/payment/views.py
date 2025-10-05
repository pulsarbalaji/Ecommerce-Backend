from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import OrderDetailsSerializer
from .models import  Payment
from products.models import OrderDetails
from auth_model.models import CustomerDetails
from django.shortcuts import get_object_or_404
import razorpay
from decimal import Decimal
from django.conf import settings
from razorpay.errors import SignatureVerificationError
# Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class CreateOrderAPIView(APIView):

    def post(self, request):
        serializer = OrderDetailsSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save()
            data = serializer.data

            if order.payment_method == "online":
                # Ensure total_amount is Decimal
                amount_in_paise = int(Decimal(order.total_amount) * 100)

                # Create Razorpay order
                razorpay_order = client.order.create({
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "payment_capture": 1
                })

                Payment.objects.create(
                    customer=order.customer,
                    order_id=razorpay_order["id"],
                    amount=float(order.total_amount),
                    method="online",
                    status="created"
                )

                return Response({
                    "status": True,
                    "order": data,
                    "razorpay_order": razorpay_order
                }, status=status.HTTP_201_CREATED)

            # For COD
            return Response({
                "status": True,
                "order": data,
                "message": "Order placed successfully with Cash on Delivery"
            }, status=status.HTTP_201_CREATED)

        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# Verify Online Payment

class VerifyPaymentAPIView(APIView):
    def post(self, request):
        order_id = request.data.get("order_id")   # backend DB order
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")

        # Verify signature
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            })
        except SignatureVerificationError:
            return Response({
                "status": False,
                "message": "Payment verification failed"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update payment
        payment = get_object_or_404(Payment, order_id=razorpay_order_id)
        payment.payment_id = razorpay_payment_id
        payment.status = "success"
        payment.save()

        # Update order
        order = get_object_or_404(OrderDetails, id=order_id)
        order.payment_status = "success"
        order.status = OrderDetails.OrderStatus.PROCESSING
        order.save()

        return Response({
            "status": True,
            "message": "Payment verified successfully",
            "order_id": order.id
        })