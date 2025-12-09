from rest_framework import serializers
from decimal import Decimal,ROUND_HALF_UP
from .models import Payment,GSTSetting,CourierChargeSetting
from products.models import OrderDetails, OrderItem
from auth_model.models import CustomerDetails
from django.db import transaction

def normalize_product_name(name: str):
    return name.strip().capitalize().replace(" ", "_")

def format_name(name: str):
    return name.replace("_", " ")

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["product", "quantity", "price", "tax", "total"]
        read_only_fields = ["price", "tax", "total"]  # ✅ client cannot control

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # optional: include product name/image for frontend
        data["product_name"] = instance.product.clean_name
        if instance.product.product_image and hasattr(instance.product.product_image, "url"):
            data["product_image"] = instance.product.product_image.url
        return data
    
# -------------------------------
# Order Details Serializer
# -------------------------------

class OrderDetailsSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = OrderDetails
        fields = [
            "id",
            "customer",
            "first_name",
            "last_name",
            "contact_number",
            "secondary_number",
            "order_number",
            "billing_address",
            "shipping_address",
            "payment_method",
            "preferred_courier_service",
            "payment_status",
            "subtotal",
            "tax",
            "shipping_cost",
            "total_amount",
            "status",
            "items",
        ]
        read_only_fields = [
            "order_number",
            "subtotal",
            "tax",
            "shipping_cost",
            "total_amount",
            "status",
            "payment_status",
        ]

    @transaction.atomic
    def create(self, validated_data):
        """
        IMPORTANT:
        - Ignore any client-sent price/tax/total
        - Compute subtotal, tax, shipping, total_amount on server
        """
        items_data = validated_data.pop("items")

        # ✅ get GST & shipping from DB settings
        gst_setting = GSTSetting.objects.first()
        courier_setting = CourierChargeSetting.objects.first()

        gst_percent = Decimal(getattr(gst_setting, "gst_percentage", 0) or 0)
        shipping_cost = Decimal(getattr(courier_setting, "courier_charge", 0) or 0)

        subtotal = Decimal("0.00")
        order_items = []

        # ---------- compute totals from DB ----------
        for item in items_data:
            product = item["product"]  # DRF gives model instance
            quantity = int(item["quantity"])

            # always use product.price from DB (or derive offer here)
            unit_price = product.price

            line_subtotal = (unit_price * quantity).quantize(Decimal("0.00"))
            line_tax = (line_subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.00"))
            line_total = (line_subtotal + line_tax).quantize(Decimal("0.00"))

            subtotal += line_subtotal
            order_items.append((product, quantity, unit_price, line_tax, line_total))

        subtotal = subtotal.quantize(Decimal("0.00"))
        tax_total = (subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.00"))

        total_amount = subtotal + tax_total + shipping_cost
        total_amount = total_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        validated_data["subtotal"] = subtotal
        validated_data["tax"] = tax_total
        validated_data["shipping_cost"] = shipping_cost
        validated_data["total_amount"] = total_amount

        # ---------- create Order header ----------
        order = OrderDetails.objects.create(**validated_data)

        # ---------- create Order items (no stock change here) ----------
        for product, quantity, unit_price, line_tax, line_total in order_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=unit_price,
                tax=line_tax,
                total=line_total,
            )

        return order

# -------------------------------
# Payment Serializer
# -------------------------------
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["razorpay_order_id", "razorpay_payment_id", "status", "amount", "method"]


# -------------------------------
# Order Tracking Serializer
# -------------------------------
class OrderTrackingSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment = serializers.SerializerMethodField()
    tax_percent = serializers.SerializerMethodField()
    

    class Meta:
        model = OrderDetails
        fields = [
            "id",
            "order_number",
            "status",
            "payment_status",
            "payment_method",
            "shipping_address",
            "billing_address",
            "preferred_courier_service",
            "courier_number",
            "subtotal",
            "tax",
            "shipping_cost",
            "total_amount",
            "ordered_at",
            "delivered_at",
            "items",
            "payment",
            "tax_percent",
        ]

    def get_payment(self, obj):
        payment = obj.payments.first()  # via related_name on FK
        return PaymentSerializer(payment).data if payment else None

    def get_tax_percent(self, obj):
        """Return GST percentage based on stored subtotal & tax."""
        try:
            if obj.subtotal and obj.subtotal > 0:
                percent = (obj.tax / obj.subtotal) * 100
                return float(round(percent, 2))   # Example: 18.0
        except:
            return 0
        return 0

class GSTSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTSetting
        fields = '__all__'


class CourierChargeSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierChargeSetting
        fields = '__all__'