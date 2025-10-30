from rest_framework import serializers
from .models import *

def normalize_category_name(name: str):
    """Convert spaces to underscores and lowercase for DB storage"""
    return name.strip().lower().replace(" ", "_")


def format_category_name(name: str):
    """Convert underscores back to spaces and title-case for response"""
    return name.replace("_", " ").title()

def normalize_product_name(name: str):
    """Convert spaces to underscores and capitalize first letter for DB storage"""
    return name.strip().capitalize().replace(" ", "_")

def format_name(name: str):
    """Convert underscores to spaces for API response"""
    return name.replace("_", " ")

class CategorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = Category
        fields = '__all__'

    def validate_category_name(self, value):
        return normalize_category_name(value)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        category_name = representation.get("category_name")
        if category_name:
            representation["category_name"] = format_category_name(category_name)
        return representation

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = Product
        fields = '__all__'

    # ✅ Normalize product name on save
    def validate_product_name(self, value):
        return normalize_product_name(value)

    # ✅ Format product name on API response
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        product_name = rep.get("product_name")
        if product_name:
            rep["product_name"] = format_name(product_name)
        category_name = rep.get("category_name")
        if category_name:
            rep["category_name"] = format_name(category_name).title()  # Optional: title case
        
            return rep


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.product_name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["product", "product_name", "quantity", "price", "tax", "total"]

class InvoiceSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    customer_name = serializers.CharField(source="order.customer.full_name", read_only=True)
    items = OrderItemSerializer(source="order.items", many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "invoice_number", "generated_at", 
            "order_number", "customer_name", 
            "items"
        ]


class OrderDetailsSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)


    class Meta:
        model = OrderDetails
        fields = [
            "id",
            "customer_name",
            "customer",
            "order_number",
            "status",
            "preferred_courier_service",
            "payment_method",
            "payment_status",
            "shipping_address",
            "billing_address",
            "subtotal",
            "tax",
            "shipping_cost",
            "total_amount",
            "delivered_at",
            "ordered_at",
            "items",
        ]
        read_only_fields = ["order_number", "ordered_at"]


    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = OrderDetails.objects.create(**validated_data)

        subtotal = 0
        for item_data in items_data:
            item = OrderItem.objects.create(order=order, **item_data)
            subtotal += item.price * item.quantity

        order.subtotal = subtotal
        order.total_amount = subtotal + order.tax + order.shipping_cost
        order.save()

        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if items_data is not None:
            instance.items.all().delete()
            subtotal = 0
            for item_data in items_data:
                item = OrderItem.objects.create(order=instance, **item_data)
                subtotal += item.price * item.quantity

            instance.subtotal = subtotal
            instance.total_amount = subtotal + instance.tax + instance.shipping_cost

        instance.save()
        return instance
    
class ContactusSerializer(serializers.ModelSerializer):

    class Meta:
        model = Contactus  
        fields = '__all__'

class OfferDetailsSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    category_name = serializers.CharField(source='category.category_name', read_only=True)

    class Meta:
        model = OfferDetails
        fields = [
            'id',
            'product',
            'category',
            'product_name',
            'category_name',
            'offer_name',
            'offer_percentage',
            'start_date',
            'end_date',
            'is_active',
            'created_at',
            'updated_at'
        ]

    # ✅ Validate start & end dates
    def validate(self, attrs):
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date.")

        # Automatically inactivate expired offers on creation
        today = timezone.now().date()
        if end_date and end_date < today:
            attrs['is_active'] = False

        return attrs

    # ✅ Normalize offer name
    def validate_offer_name(self, value):
        return value.strip().title()




class ProductWithOfferSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    offer_price = serializers.SerializerMethodField()
    offer_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "category_name",
            "product_name",
            "product_description",
            "price",
            "offer_percentage",
            "offer_price",
            "product_image",
            "stock_quantity",
            "is_available",
            "average_rating",
            "created_at",
            "updated_at",
            "category",
            "created_by",
        ]

    # --- Offer calculation ---
    def get_offer_price(self, obj):
        offer = obj.offers.filter(is_active=True).first()
        if offer and offer.offer_percentage:
            discount = obj.price * (offer.offer_percentage / 100)
            return round(obj.price - discount, 2)
        return None

    def get_offer_percentage(self, obj):
        offer = obj.offers.filter(is_active=True).first()
        return offer.offer_percentage if offer and offer.offer_percentage else None

    # --- Normalize on save ---
    def validate_product_name(self, value):
        return normalize_product_name(value)

    # --- Format on response ---
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        product_name = rep.get("product_name")
        if product_name:
            rep["product_name"] = format_name(product_name)
            
        category_name = rep.get("category_name")
        if category_name:
            rep["category_name"] = format_name(category_name).title()  # Optional: title case

        return rep

#Dashboard Serializers

class DashboardStatsSerializer(serializers.Serializer):
    total_sales = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_orders = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    total_products = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()

# Sales Chart Serializer
class SalesChartSerializer(serializers.Serializer):
    date = serializers.DateField()
    sales = serializers.DecimalField(max_digits=15, decimal_places=2)

# Top Products Serializer
class TopProductSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField(source="product__product_name")
    total_sold = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)

# Recent Orders Serializer
class RecentOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    order_status = serializers.CharField(source="status")  # map `status` field

    class Meta:
        model = OrderDetails
        fields = ["order_number", "total_amount", "order_status", "ordered_at", "customer_name", "customer_email"]

    def get_customer_name(self, obj):
        return obj.customer.full_name

    def get_customer_email(self, obj):
        return obj.customer.auth.email if obj.customer.auth else None


# Low Stock Products Serializer
class LowStockProductSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "product_name", "category_name", "stock_quantity"]

    def get_category_name(self, obj):
        return obj.category.category_name if obj.category else None


# New Customers Serializer
class NewCustomerSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()

    class Meta:
        model = CustomerDetails
        fields = ["id", "full_name", "email", "created_at"]

    def get_email(self, obj):
        return obj.auth.email if obj.auth else None
    



class FillterProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.category_name", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "product_name", "category_name"]  # ✅ FIXED (must be a list or tuple)

    def validate_product_name(self, value):
        return normalize_product_name(value)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # ✅ Clean formatting
        if rep.get("product_name"):
            rep["product_name"] = format_name(rep["product_name"])
        if rep.get("category_name"):
            rep["category_name"] = format_name(rep["category_name"]).title()
        return rep