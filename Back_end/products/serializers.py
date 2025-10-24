from rest_framework import serializers
from .models import *

class CategorySerializer(serializers.ModelSerializer):

    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    class Meta:
        model = Category  
        fields = '__all__'
        
class ProductSerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(source='category.category_name', read_only=True)
    class Meta:
        model = Product  
        fields = '__all__'

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
            'is_active',
            'created_at',
            'updated_at'
        ]

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

    def get_offer_price(self, obj):
        offer = obj.offers.filter(is_active=True).first()
        if not offer:
            return None  # ✅ explicitly return null if inactive or no offer
        if offer.offer_percentage:
            discount = obj.price * (offer.offer_percentage / 100)
            return round(obj.price - discount, 2)
        return None

    def get_offer_percentage(self, obj):
        offer = obj.offers.filter(is_active=True).first()
        if not offer or not offer.offer_percentage:
            return None  # ✅ explicitly return null if inactive or no offer
        return offer.offer_percentage
    

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