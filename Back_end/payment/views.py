from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from .serializers import OrderDetailsSerializer,OrderTrackingSerializer,GSTSettingSerializer,CourierChargeSettingSerializer
from .models import  Payment,GSTSetting,CourierChargeSetting
from products.models import OrderDetails,Product,OrderItem
from auth_model.models import CustomerDetails
from django.shortcuts import get_object_or_404
import razorpay
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from razorpay.errors import SignatureVerificationError
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
# Razorpay client

RESERVATION_DURATION = timedelta(minutes=5)

class OrderHistoryPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 50
class ReserveOrderAPIView(APIView):
    def post(self, request):
        items = request.data.get("items", [])
        payment_method = request.data.get("payment_method", "online")
        auth_id = request.data.get("auth_id")

        # Get customer
        try:
            customer = CustomerDetails.objects.get(auth_id=auth_id)
        except CustomerDetails.DoesNotExist:
            return Response({"status": False, "message": "Customer not found"}, status=404)

        try:
            with transaction.atomic():

                # ⭐ FULL TOTAL FROM FRONTEND (subtotal + gst + shipping)
                full_total_amount = Decimal(request.data.get("total_amount", "0.00"))

                # Reserve stock
                for item in items:
                    product_id = item["product"]
                    quantity = int(item["quantity"])
                    product = Product.objects.select_for_update().get(id=product_id)

                    # Clear expired reservations
                    if product.reserved_until and product.reserved_until < timezone.now():
                        product.reserved_by = None
                        product.reserved_until = None
                        product.save()

                    # Check if reserved by someone else
                    if (
                        product.reserved_by
                        and product.reserved_by != customer
                        and product.reserved_until > timezone.now()
                    ):
                        raise ValueError(
                            f"Sorry, {product.product_name} is being checked out by another user."
                        )

                    # Stock check
                    if product.stock_quantity < quantity:
                        raise ValueError(
                            f"Insufficient stock for {product.product_name}. Only {product.stock_quantity} left."
                        )

                    # Reserve for this customer
                    product.reserved_by = customer
                    product.reserved_until = timezone.now() + RESERVATION_DURATION
                    product.save()

                # --------------------------
                # CREATE RAZORPAY ORDER
                # --------------------------
                razorpay_order = None
                if payment_method == "online":

                    amount_in_paise = int(full_total_amount * 100)

                    razorpay_order = client.order.create({
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "payment_capture": 1
                    })

                    Payment.objects.create(
                        customer=customer,
                        order_id=razorpay_order["id"],
                        amount=float(full_total_amount),   # ✔ FIXED
                        method="online",
                        status="created"
                    )

                return Response({
                    "status": True,
                    "message": "Products reserved successfully.",
                    "razorpay_order": razorpay_order,
                }, status=201)

        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=404)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=500)


# ===============================================================
# 2️⃣ Verify Razorpay payment and create order
# ===============================================================
class VerifyPaymentAndCreateOrderAPIView(APIView):
    """
    Step 2: Verify Razorpay payment & finalize order
    """

    def post(self, request):
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")
        order_data = request.data.get("order_data")

        auth_id = request.data.get("auth_id")

        try:
            customer = CustomerDetails.objects.get(auth_id=auth_id)
        except CustomerDetails.DoesNotExist:
            return Response({"status": False, "message": "Customer not found"}, status=404)

        # ---------------- verify Razorpay signature ----------------
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            })
        except SignatureVerificationError:
            return Response({"status": False, "message": "Payment verification failed"}, status=400)

        items_data = order_data.get("items", [])
        serializer = OrderDetailsSerializer(data=order_data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                order = serializer.save(customer=customer, payment_status="success")

                for item in items_data:
                    product = Product.objects.select_for_update().get(id=item["product"])
                    quantity = int(item["quantity"])

                    # ✅ ensure reserved for this user
                    if product.reserved_by_id != customer.id:
                        raise ValueError(
                            f"{product.product_name} reservation not found or expired."
                        )

                    if product.stock_quantity < quantity:
                        raise ValueError(
                            f"Insufficient stock for {product.product_name}"
                        )

                    # ✅ deduct stock and clear reservation
                    product.stock_quantity -= quantity
                    if product.stock_quantity <= 0:
                        product.is_available = False
                    product.reserved_by = None
                    product.reserved_until = None
                    product.save()

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=item["price"],
                        total=item["total"],
                    )

                # ✅ update payment record
                Payment.objects.filter(order_id=razorpay_order_id).update(
                    payment_id=razorpay_payment_id,
                    status="success"
                )

                return Response({
                    "status": True,
                    "message": "Payment verified & order placed successfully.",
                    "order": serializer.data,
                }, status=201)

        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=404)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=500)


# ===============================================================
# 3️⃣ Create COD order (no Razorpay)
# ===============================================================
class CreateCODOrderAPIView(APIView):
    """
    Step 2 (COD): Create order directly and finalize stock
    """

    def post(self, request):
        order_data = request.data.get("order_data")
        items_data = order_data.get("items", [])
        auth_id = request.data.get("auth_id")

        try:
            customer = CustomerDetails.objects.get(auth_id=auth_id)
        except CustomerDetails.DoesNotExist:
            return Response({"status": False, "message": "Customer not found"}, status=404)

        serializer = OrderDetailsSerializer(data=order_data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                order = serializer.save(customer=customer, payment_method="COD", payment_status="pending")

                for item in items_data:
                    product = Product.objects.select_for_update().get(id=item["product"])
                    quantity = int(item["quantity"])

                    # ✅ same reservation logic for COD
                    if (
                        product.reserved_by
                        and product.reserved_by != customer
                        and product.reserved_until > timezone.now()
                    ):
                        raise ValueError(
                            f"Sorry, {product.product_name} is being checked out by another user."
                        )

                    if product.stock_quantity < quantity:
                        raise ValueError(
                            f"Insufficient stock for {product.product_name}"
                        )

                    # ✅ deduct stock
                    product.stock_quantity -= quantity
                    if product.stock_quantity <= 0:
                        product.is_available = False
                    product.reserved_by = None
                    product.reserved_until = None
                    product.save()

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=item["price"],
                        total=item["total"],
                    )

                return Response({
                    "status": True,
                    "message": "Order placed successfully with Cash on Delivery.",
                    "order": serializer.data,
                }, status=201)

        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=500)
        
class CreateOrderAPIView(APIView):

    def post(self, request):
        serializer = OrderDetailsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"status": False, "errors": serializer.errors}, status=400)

        items_data = request.data.get("items", [])
        user = request.user  # adjust if using custom authentication
        try:
            customer = CustomerDetails.objects.get(user=user)
        except CustomerDetails.DoesNotExist:
            return Response({"status": False, "message": "Customer not found"}, status=404)

        try:
            with transaction.atomic():
                # ✅ Pre-check & stock locking
                for item in items_data:
                    product_id = item["product"]
                    quantity = int(item["quantity"])
                    product = Product.objects.select_for_update().get(id=product_id)

                    # 🕓 Clear expired reservations
                    if product.reserved_until and product.reserved_until < timezone.now():
                        product.reserved_by = None
                        product.reserved_until = None
                        product.save()

                    # ⚠️ Low stock reservation logic
                    if product.stock_quantity <= 5:
                        if product.reserved_by and product.reserved_by != customer and product.reserved_until > timezone.now():
                            raise ValueError(f"Sorry, {product.product_name} is currently being checked out by another user.")

                        # Reserve for this user
                        product.reserved_by = customer
                        product.reserved_until = timezone.now() + RESERVATION_DURATION
                        product.save()
                    else:
                        # ✅ For normal stock, just check availability
                        if product.stock_quantity < quantity:
                            raise ValueError(f"Sorry, only {product.stock_quantity} left in stock for {product.product_name}.")

                # 🧾 Create the order safely
                order = serializer.save(customer=customer)

                for item in items_data:
                    product_id = item["product"]
                    quantity = int(item["quantity"])
                    price = Decimal(item["price"])
                    total = Decimal(item["total"])

                    product = Product.objects.select_for_update().get(id=product_id)

                    # Check again before deduction
                    if product.stock_quantity < quantity:
                        raise ValueError(f"Insufficient stock for {product.product_name}")

                    # Deduct stock
                    product.stock_quantity -= quantity
                    if product.stock_quantity <= 0:
                        product.is_available = False
                        product.reserved_by = None
                        product.reserved_until = None
                    product.save()

                    # Create order item
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=price,
                        total=total,
                    )

                # 💳 Handle online payment
                if order.payment_method == "online":
                    amount_in_paise = int(Decimal(order.total_amount) * 100)
                    razorpay_order = client.order.create({
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "payment_capture": 1,
                    })

                    Payment.objects.create(
                        customer=order.customer,
                        order_id=razorpay_order["id"],
                        amount=float(order.total_amount),
                        method="online",
                        status="created",
                    )

                    return Response({
                        "status": True,
                        "order": serializer.data,
                        "razorpay_order": razorpay_order,
                        "message": "Products reserved. Proceed to payment."
                    }, status=status.HTTP_201_CREATED)

                # 💵 Handle COD success
                return Response({
                    "status": True,
                    "order": serializer.data,
                    "message": "Order placed successfully with Cash on Delivery."
                }, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=404)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=500)
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
        customer_id = request.data.get("customer_id") or (order_data or {}).get("customer")

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
    


    