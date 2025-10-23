from rest_framework import serializers
from decimal import Decimal
from .models import Payment
from products.models import OrderDetails, OrderItem
from auth_model.models import CustomerDetails


# -------------------------------
# Order Item Serializer
# -------------------------------
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.product_name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["product", "product_name", "quantity", "price", "tax", "total"]

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

    def create(self, validated_data):
        items_data = validated_data.pop("items")

        # --- Calculate subtotal, tax, and total ---
        subtotal = sum(Decimal(item["price"]) * item["quantity"] for item in items_data)
        tax_total = sum(Decimal(item.get("tax", 0)) for item in items_data)

        validated_data["subtotal"] = subtotal
        validated_data["tax"] = tax_total
        validated_data["total_amount"] = subtotal + tax_total + Decimal(
            validated_data.get("shipping_cost", 0)
        )

        order = OrderDetails.objects.create(**validated_data)

        # --- Create order items ---
        for item in items_data:
            OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                price=Decimal(item["price"]),
                tax=Decimal(item.get("tax", 0)),
                total=Decimal(item["price"]) * item["quantity"],
            )

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
