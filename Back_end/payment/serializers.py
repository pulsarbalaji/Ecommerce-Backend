from rest_framework import serializers
from .models import  Payment
from decimal import Decimal
from products.models import OrderDetails,OrderItem,Product
from auth_model.models import CustomerDetails

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price', 'tax', 'total']
        read_only_fields = ['total']

    def create(self, validated_data):
        validated_data['total'] = Decimal(validated_data['price']) * validated_data['quantity']
        return super().create(validated_data)


class OrderDetailsSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=CustomerDetails.objects.all())

    class Meta:
        model = OrderDetails
        fields = [
            'id', 'customer', 'billing_address', 'shipping_address', 
            'payment_method', 'payment_status', 'subtotal', 'tax', 
            'shipping_cost', 'total_amount', 'status', 'items'
        ]
        read_only_fields = ['subtotal', 'tax', 'total_amount', 'status', 'payment_status']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Calculate subtotal and tax
        subtotal = sum(Decimal(item['price']) * item['quantity'] for item in items_data)
        tax_total = sum(Decimal(item.get('tax', 0)) for item in items_data)
        
        validated_data['subtotal'] = subtotal
        validated_data['tax'] = tax_total
        validated_data['total_amount'] = subtotal + tax_total + Decimal(validated_data.get('shipping_cost', 0))
        
        order = OrderDetails.objects.create(**validated_data)
        
        # Create order items
        for item in items_data:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                price=Decimal(item['price']),
                tax=Decimal(item.get('tax', 0)),
                total=Decimal(item['price']) * item['quantity']
            )
        
        return order