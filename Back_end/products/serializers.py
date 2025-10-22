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
        if offer and offer.offer_percentage:
            discount = obj.price * (offer.offer_percentage / 100)
            return round(obj.price - discount, 2)
        return None

    def get_offer_percentage(self, obj):
        offer = obj.offers.filter(is_active=True).first()
        return offer.offer_percentage if offer else None