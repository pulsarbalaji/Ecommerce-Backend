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
    product_name = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["product","product_image", "product_name", "quantity", "price", "tax", "total"]

    # ✅ Format product name for API response
    def get_product_name(self, obj):
        if obj.product and obj.product.product_name:
            return format_name(obj.product.product_name)
        return None

    def get_product_image(self, obj):
        if obj.product.product_image and hasattr(obj.product.product_image, "url"):
            return obj.product.product_image.url  
        return None

    def create(self, validated_data):
        validated_data["total"] = Decimal(validated_data["price"]) * validated_data["quantity"]
        return super().create(validated_data)

# -------------------------------
# Order Details Serializer
# -------------------------------


class OrderDetailsSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=CustomerDetails.objects.all())
    order_number = serializers.CharField(read_only=True)

    tax_percent = serializers.DecimalField(
    max_digits=5, decimal_places=2, write_only=True, required=False
)


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
            "tax_percent",   # ← ADD THIS FIELD
        ]
        read_only_fields = ["subtotal", "tax", "total_amount", "status", "payment_status"]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        # tax_percent is write_only; default to 0 if not provided
        gst_percent = Decimal(validated_data.pop("tax_percent", 0))
        # shipping_cost might be missing or a string/Decimal — coerce to Decimal
        shipping_cost = Decimal(validated_data.get("shipping_cost", 0))

        # ---------- SUBTOTAL ----------
        subtotal = sum(
            (Decimal(item["price"]) * int(item["quantity"]))
            for item in items_data
        ).quantize(Decimal("0.00"))

        # ---------- TAX ----------
        tax_total = (subtotal * gst_percent / Decimal("100")).quantize(Decimal("0.00"))

        # ---------- TOTAL ---------- (round to nearest integer rupee)
        total_amount = subtotal + tax_total + shipping_cost
        # round to nearest integer with half-up behavior
        total_amount = total_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        validated_data["subtotal"] = subtotal
        validated_data["tax"] = tax_total
        validated_data["total_amount"] = total_amount

        # ---------- CREATE ORDER ----------
        order = OrderDetails.objects.create(**validated_data)

        # ---------- CREATE ORDER ITEMS ----------
        for item in items_data:
            # If item["product"] is a PK, you should resolve it to instance here.
            # Many nested serializers pass actual model instances already; adjust as needed.
            product = item["product"]
            price = Decimal(item["price"])
            quantity = int(item["quantity"])

            # tax for line
            line_tax = (price * quantity * gst_percent / Decimal("100")).quantize(Decimal("0.00"))
            # line total usually includes price*qty + tax (adjust if your model differs)
            line_total = (price * quantity + line_tax).quantize(Decimal("0.00"))

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price,
                tax=line_tax,
                total=line_total,
            )

            # decrement stock and save — ensure product is a model instance
            if hasattr(product, "stock_quantity"):
                product.stock_quantity = max(product.stock_quantity - quantity, 0)
                product.save(update_fields=["stock_quantity"])

        return order


# -------------------------------
# Payment Serializer
# -------------------------------
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["order_id", "payment_id", "status", "amount", "method"]


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
        payment = Payment.objects.filter(
            customer=obj.customer, order_id=obj.order_number
        ).first()
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