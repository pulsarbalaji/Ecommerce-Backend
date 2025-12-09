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
from decimal import Decimal, ROUND_HALF_UP

# Razorpay client

RESERVATION_DURATION = timedelta(minutes=5)

class OrderHistoryPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 50

class ReserveOrderAPIView(APIView):

    def post(self, request):
        """
        Step 1: Validate stock, compute totals from DB, create Razorpay order, reserve items.
        """
        items = request.data.get("items", [])
        payment_method = request.data.get("payment_method", "online")

        # ALWAYS from authenticated user
        try:
            customer = CustomerDetails.objects.get(auth_id=request.user.id)
        except CustomerDetails.DoesNotExist:
            return Response({"status": False, "message": "Customer not found"}, status=404)

        if not items:
            return Response({"status": False, "message": "No items provided"}, status=400)

        try:
            with transaction.atomic():
                subtotal = Decimal("0.00")
                gst_setting = GSTSetting.objects.first()
                courier_setting = CourierChargeSetting.objects.first()

                gst_percent = Decimal(getattr(gst_setting, "gst_percentage", 0) or 0)
                shipping_cost = Decimal(getattr(courier_setting, "courier_charge", 0) or 0)

                # ---------- Reserve stock & compute subtotal ----------
                for item in items:
                    product_id = item["product"]
                    quantity = int(item["quantity"])

                    product = Product.objects.select_for_update().get(id=product_id)

                    # Clear expired reservation
                    if product.reserved_until and product.reserved_until < timezone.now():
                        product.reserved_by = None
                        product.reserved_until = None
                        product.save()

                    # Check if reserved by another user
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
                            f"Insufficient stock for {product.product_name}. Only {product.stock_quantity} left."
                        )

                    # compute price (you can enhance: respect offers here)
                    unit_price = product.price
                    subtotal += unit_price * quantity

                    # Reserve for this customer
                    product.reserved_by = customer
                    product.reserved_until = timezone.now() + RESERVATION_DURATION
                    product.save()

                subtotal = subtotal.quantize(Decimal("0.00"))
                gst_amount = (subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.00"))
                total_amount = (subtotal + gst_amount + shipping_cost).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

                razorpay_order = None

                if payment_method == "online":
                    amount_in_paise = int(total_amount * 100)

                    razorpay_order = client.order.create({
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "payment_capture": 1,
                    })

                    Payment.objects.create(
                        customer=customer,
                        razorpay_order_id=razorpay_order["id"],
                        amount=total_amount,
                        method="online",
                        status="created",
                    )

                return Response(
                    {
                        "status": True,
                        "message": "Products reserved successfully.",
                        "razorpay_order": razorpay_order,
                        "totals": {
                            "subtotal": subtotal,
                            "gst_percent": float(gst_percent),
                            "gst_amount": gst_amount,
                            "shipping_cost": shipping_cost,
                            "total_amount": total_amount,
                        },
                    },
                    status=201,
                )

        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=404)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=500)

class VerifyPaymentAndCreateOrderAPIView(APIView):
    """
    Step 2: Verify Razorpay payment, re-check stock, create Order, deduct stock.
    """

    def post(self, request):
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")
        order_data = request.data.get("order_data")  # only structural, not trusted for money

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, order_data]):
            return Response({"status": False, "message": "Missing required fields"}, status=400)

        # get customer from auth
        try:
            customer = CustomerDetails.objects.get(auth_id=request.user.id)
        except CustomerDetails.DoesNotExist:
            return Response({"status": False, "message": "Customer not found"}, status=404)

        # 1️⃣ verify Razorpay signature
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            })
        except SignatureVerificationError:
            return Response({"status": False, "message": "Payment verification failed"}, status=400)

        # 2️⃣ fetch payment from Razorpay & match amount/status
        try:
            payment_info = client.payment.fetch(razorpay_payment_id)
        except Exception as e:
            return Response({"status": False, "message": "Unable to fetch payment info"}, status=400)

        if payment_info.get("status") != "captured":
            return Response({"status": False, "message": "Payment not captured"}, status=400)

        # Payment row created at reserve step
        pay_rec = Payment.objects.filter( razorpay_order_id=razorpay_order_id, customer=customer).first()
        if not pay_rec:
            return Response({"status": False, "message": "Payment record not found"}, status=404)

        expected_paise = int(Decimal(str(pay_rec.amount)) * 100)
        if int(payment_info.get("amount", 0)) != expected_paise:
            return Response({"status": False, "message": "Payment amount mismatch"}, status=400)

        # 3️⃣ create actual order & deduct stock
        items_data = order_data.get("items", [])

        # enforce customer from auth, override any client-sent customer
        order_data["customer"] = customer.id

        serializer = OrderDetailsSerializer(data=order_data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # check stock & reservation again before commit
                for item in items_data:
                    product = Product.objects.select_for_update().get(id=item["product"])
                    quantity = int(item["quantity"])

                    if product.reserved_by_id != customer.id:
                        raise ValueError(f"{product.product_name} reservation not found or expired.")

                    if product.stock_quantity < quantity:
                        raise ValueError(f"Insufficient stock for {product.product_name}")

                # create order & items (serializer computes totals from DB)
                order = serializer.save(
                    payment_status=OrderDetails.PaymentStatus.SUCCESS,
                    status=OrderDetails.OrderStatus.ORDER_CONFIRMED,
                    payment_method=OrderDetails.PaymentMethod.ONLINE,
                )

                # now deduct stock & clear reservation
                for item in order.items.all():
                    product = item.product
                    quantity = item.quantity

                    if product.stock_quantity < quantity:
                        raise ValueError(f"Insufficient stock for {product.product_name}")

                    product.stock_quantity -= quantity
                    if product.stock_quantity <= 0:
                        product.is_available = False
                    product.reserved_by = None
                    product.reserved_until = None
                    product.save()

                # update Payment record
                pay_rec.order = order
                pay_rec. razorpay_order_id = razorpay_payment_id
                pay_rec.status = "success"
                pay_rec.save(update_fields=["order", "razorpay_payment_id", "status"])

                return Response(
                    {
                        "status": True,
                        "message": "Payment verified & order placed successfully.",
                        "order": OrderDetailsSerializer(order).data,
                    },
                    status=201,
                )

        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=404)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=500)

class CreateCODOrderAPIView(APIView):

    def post(self, request):
        order_data = request.data.get("order_data")
        items_data = order_data.get("items", [])

        try:
            customer = CustomerDetails.objects.get(auth_id=request.user.id)
        except CustomerDetails.DoesNotExist:
            return Response({"status": False, "message": "Customer not found"}, status=404)

        # enforce customer from auth
        order_data["customer"] = customer.id

        serializer = OrderDetailsSerializer(data=order_data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # stock lock & validation
                for item in items_data:
                    product = Product.objects.select_for_update().get(id=item["product"])
                    quantity = int(item["quantity"])

                    if product.stock_quantity < quantity:
                        raise ValueError(
                            f"Insufficient stock for {product.product_name}. Only {product.stock_quantity} left."
                        )

                # create order & items (totals computed by serializer)
                order = serializer.save(
                    payment_method=OrderDetails.PaymentMethod.COD,
                    payment_status=OrderDetails.PaymentStatus.PENDING,
                )

                # deduct stock
                for item in order.items.all():
                    product = item.product
                    quantity = item.quantity

                    if product.stock_quantity < quantity:
                        raise ValueError(f"Insufficient stock for {product.product_name}")

                    product.stock_quantity -= quantity
                    if product.stock_quantity <= 0:
                        product.is_available = False
                    product.save()

                return Response(
                    {
                        "status": True,
                        "message": "Order placed successfully with Cash on Delivery.",
                        "order": OrderDetailsSerializer(order).data,
                    },
                    status=201,
                )

        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=404)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=500)

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
    


    