from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from .serializers import OrderDetailsSerializer,OrderTrackingSerializer,GSTSettingSerializer,CourierChargeSettingSerializer
from .models import  Payment,GSTSetting,CourierChargeSetting
from products.models import OrderDetails
from auth_model.models import CustomerDetails
from django.shortcuts import get_object_or_404
import razorpay
from decimal import Decimal
from django.conf import settings
from razorpay.errors import SignatureVerificationError
from rest_framework.pagination import PageNumberPagination
# Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class OrderHistoryPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 50

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

# 1️⃣ Create a Razorpay order (no DB order yet)
class CreateRazorpayOrderAPIView(APIView):
    def post(self, request):
        amount = request.data.get("amount")
        if not amount:
            return Response({"error": "Amount is required"}, status=400)

        try:
            amount_in_paise = int(Decimal(amount) * 100)
            razorpay_order = client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "payment_capture": 1
            })

            return Response({
                "status": True,
                "razorpay_order": razorpay_order
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=400)


# 2️⃣ Verify Razorpay payment and then create actual order
class VerifyPaymentAndCreateOrderAPIView(APIView):
    def post(self, request):
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")
        order_data = request.data.get("order_data")
        customer_id = request.data.get("customer_id")

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, order_data, customer_id]):
            return Response({"status": False, "message": "Missing required fields"}, status=400)

        # ✅ Verify Razorpay signature
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            })
        except SignatureVerificationError:
            return Response({"status": False, "message": "Payment verification failed"}, status=400)

        # ✅ Create Order only after successful payment
        serializer = OrderDetailsSerializer(data=order_data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(payment_status="success", status=OrderDetails.OrderStatus.ORDER_CONFIRMED)

        # ✅ Save Payment record
        Payment.objects.create(
            customer_id=customer_id,
            order_id=razorpay_order_id,
            payment_id=razorpay_payment_id,
            amount=float(order.total_amount),
            method="online",
            status="success"
        )

        return Response({
            "status": True,
            "message": "Payment verified & order created successfully",
            "order": serializer.data
        }, status=status.HTTP_201_CREATED)

class OrderTrackingAPIView(APIView):
    """
    Track order by order_number.
    """

    def get(self, request, order_number):
        try:
            order = OrderDetails.objects.prefetch_related("items").get(order_number=order_number)
            serializer = OrderTrackingSerializer(order)
            return Response({
                "message": "Order fetched successfully",
                "success": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except OrderDetails.DoesNotExist:
            return Response({
                "message": "Order not found",
                "success": False,
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({
                "message": str(e),
                "success": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class CustomerOrderHistoryView(generics.ListAPIView):
    serializer_class = OrderDetailsSerializer
    pagination_class = OrderHistoryPagination

    def get_queryset(self):
        customer_id = self.kwargs.get("customer_id")
        return OrderDetails.objects.filter(customer_id=customer_id).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        customer_id = self.kwargs.get("customer_id")
        queryset = self.get_queryset()

        if not queryset.exists():
            return Response(
                {"message": "No orders found for this customer."},
                status=status.HTTP_404_NOT_FOUND,
            )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    

class GSTSettingView(APIView):
    def get(self, request):
        setting = GSTSetting.objects.get(id=1)
        serializer = GSTSettingSerializer(setting)
        return Response(serializer.data)

    def put(self, request):
        setting = GSTSetting.objects.get(id=1)
        serializer = GSTSettingSerializer(setting, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CourierChargeSettingView(APIView):
    def get(self, request):
        setting = CourierChargeSetting.objects.get(id=1)
        serializer = CourierChargeSettingSerializer(setting)
        return Response(serializer.data)

    def put(self, request):
        setting = CourierChargeSetting.objects.get(id=1)
        serializer = CourierChargeSettingSerializer(setting, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


    