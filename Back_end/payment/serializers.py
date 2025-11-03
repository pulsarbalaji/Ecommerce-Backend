from rest_framework import serializers
from decimal import Decimal
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
        read_only_fields = ["subtotal", "tax", "total_amount", "status", "payment_status"]
    
    @transaction.atomic  # ✅ all operations below happen in one DB transaction
    def create(self, validated_data):
        items_data = validated_data.pop("items")

        # --- Calculate subtotal, tax, and total ---
        subtotal = sum(Decimal(item["price"]) * item["quantity"] for item in items_data)
        tax_total = sum(Decimal(item.get("tax", 0)) for item in items_data)
        shipping_cost = Decimal(validated_data.get("shipping_cost", 0))

        validated_data["subtotal"] = subtotal
        validated_data["tax"] = tax_total
        validated_data["total_amount"] = subtotal + tax_total + shipping_cost

        # --- Create order ---
        order = OrderDetails.objects.create(**validated_data)

        # --- Create order items & update stock ---
        for item in items_data:
            product = item["product"]

            # ✅ Check stock availability
            if product.stock_quantity < item["quantity"]:
                raise serializers.ValidationError(
                    f"Insufficient stock for product: {product.product_name}"
                )

            # ✅ Create order item
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item["quantity"],
                price=Decimal(item["price"]),
                tax=Decimal(item.get("tax", 0)),
                total=Decimal(item["price"]) * item["quantity"],
            )

            # ✅ Reduce product stock
            product.stock_quantity -= item["quantity"]
            product.save(update_fields=["stock_quantity"])

        # ✅ Return order instance
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
            "subtotal",
            "tax",
            "shipping_cost",
            "total_amount",
            "ordered_at",
            "delivered_at",
            "items",
            "payment",
        ]

    def get_payment(self, obj):
        payment = Payment.objects.filter(
            customer=obj.customer, order_id=obj.order_number
        ).first()
        return PaymentSerializer(payment).data if payment else None


class GSTSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTSetting
        fields = '__all__'


class CourierChargeSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierChargeSetting
        fields = '__all__'