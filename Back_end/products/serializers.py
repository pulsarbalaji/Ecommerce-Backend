from rest_framework import serializers
from .models import *
from .utils import get_display_product
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum

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
    tax_percent = serializers.SerializerMethodField()


    class Meta:
        model = OrderDetails
        fields = [
            "id",
            "customer_name",
            "customer",
            "contact_number",
            "order_number",
            "status",
            "is_printed",
            "preferred_courier_service",
            "courier_number",
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
            "tax_percent"
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

    def get_tax_percent(self, obj):
        """Return GST percentage based on stored subtotal & tax."""
        try:
            if obj.subtotal and obj.subtotal > 0:
                percent = (obj.tax / obj.subtotal) * 100
                return float(round(percent, 2))   # Example: 18.0
        except:
            return 0
        return 0
    
    
    
    
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
    active_variant = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()


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
            "quantity",
            "quantity_unit",
            "stock_quantity",
            "available_stock",
            "is_available",
            "average_rating",
            "active_variant",
            "created_at",
            "updated_at",
            "category",
            "created_by",
        ]

    # ---------------------------------------
    #  OFFER HELPERS  (MUST NOT REMOVE)
    # ---------------------------------------
    def _offer_is_active(self, offer):
        """Check if an offer is active."""
        if not offer or not offer.is_active:
            return False

        if not offer.offer_percentage:
            return False

        today = timezone.now().date()
        try:
            if offer.start_date and offer.end_date:
                return offer.start_date <= today <= offer.end_date
        except:
            return True

        return True
    
    def get_available_stock(self, obj):
        """Stock shown to users = total stock - sum of all active reservations"""

        active_qty = ProductReservation.objects.filter(
            product=obj,
            reserved_until__gt=timezone.now()
        ).aggregate(total=Sum("quantity"))["total"] or 0

        return obj.stock_quantity - active_qty

    def _get_active_offer(self, obj):
        """Return first valid offer from prefetched list."""
        for off in obj.offers.all():
            if self._offer_is_active(off):
                return off
        return None

    # ---------------------------------------
    # OFFER DISPLAY VALUES
    # ---------------------------------------
    def get_offer_price(self, obj):
        offer = self._get_active_offer(obj)
        if offer:
            price = Decimal(obj.price)
            pct = Decimal(offer.offer_percentage) / Decimal(100)
            discounted = price * (Decimal(1) - pct)
            return float(discounted.quantize(Decimal("0.01")))
        return None

    def get_offer_percentage(self, obj):
        offer = self._get_active_offer(obj)
        return offer.offer_percentage if offer else None

    # ---------------------------------------
    # VARIANT when main OUT OF STOCK
    # ---------------------------------------
    def get_active_variant(self, obj):
        if obj.parent:
            return None

        if obj.stock_quantity <= 0 or obj.is_available is False:
            v = obj.variants.filter(is_available=True, stock_quantity__gt=0).first()
            if v:
                return {
                    "id": v.id,
                    "product_name": v.product_name,
                    "price": float(v.price),
                    "offer_price": self.get_offer_price(v),
                    "quantity": v.quantity,
                    "quantity_unit": v.quantity_unit,
                    "stock_quantity": v.stock_quantity,
                }
        return None

    # ---------------------------------------
    # FINAL OUTPUT LOGIC
    # ---------------------------------------
    def to_representation(self, instance):
        rep = super().to_representation(instance)

        raw_cat = rep.get("category_name")
        if raw_cat:
            rep["category_name"] = format_category_name(raw_cat)

        main_offer = self._get_active_offer(instance)

        # Find variant with stock
        variant_in_stock = None
        for v in instance.variants.all():
            if v.is_available and v.stock_quantity > 0:
                variant_in_stock = v
                break

        # Find variant with offer
        variant_with_offer = None
        for v in instance.variants.all():
            if v.is_available and v.stock_quantity > 0:
                if self._get_active_offer(v):
                    variant_with_offer = v
                    break

        # ----------------------------------------------------------
        # RULE A — MAIN HAS OFFER  → ALWAYS SHOW MAIN
        # ----------------------------------------------------------
        if main_offer:
            rep["product_name"] = format_name(rep["product_name"])
            rep["offer_price"] = self.get_offer_price(instance)
            rep["offer_percentage"] = self.get_offer_percentage(instance)
            return rep

        # ----------------------------------------------------------
        # RULE B — MAIN NO OFFER + VARIANT HAS OFFER → SHOW VARIANT
        # ----------------------------------------------------------
        if variant_with_offer:
            v = variant_with_offer
            rep["id"] = v.id
            rep["product_name"] = format_name(v.product_name)
            rep["price"] = float(v.price)
            rep["offer_price"] = self.get_offer_price(v)
            rep["offer_percentage"] = self.get_offer_percentage(v)
            rep["quantity"] = v.quantity
            rep["quantity_unit"] = v.quantity_unit
            rep["stock_quantity"] = v.stock_quantity
            rep["product_image"] = v.product_image.url if v.product_image else None
            rep["is_available"] = v.is_available
            rep["active_variant"] = None
            return rep

        # ----------------------------------------------------------
        # RULE C — NO OFFER ANYWHERE → STOCK LOGIC
        # ----------------------------------------------------------

        # main in stock → show main
        if instance.stock_quantity > 0:
            rep["product_name"] = format_name(rep["product_name"])
            rep["offer_price"] = None
            rep["offer_percentage"] = None
            return rep

        # main out of stock → variant in stock → show variant
        if variant_in_stock:
            v = variant_in_stock
            rep["id"] = v.id
            rep["product_name"] = format_name(v.product_name)
            rep["price"] = float(v.price)
            rep["offer_price"] = None
            rep["offer_percentage"] = None
            rep["quantity"] = v.quantity
            rep["quantity_unit"] = v.quantity_unit
            rep["stock_quantity"] = v.stock_quantity
            rep["product_image"] = v.product_image.url if v.product_image else None
            rep["is_available"] = v.is_available
            rep["active_variant"] = None
            return rep

        # main + variant out of stock → show main
        rep["product_name"] = format_name(rep["product_name"])
        rep["offer_price"] = None
        rep["offer_percentage"] = None
        return rep


#Dashboard Serializers

class DashboardStatsSerializer(serializers.Serializer):
    total_sales = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_orders = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    total_products = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    delivered_orders = serializers.IntegerField()

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

class FavoriteProductSerializer(serializers.ModelSerializer):
    product = ProductWithOfferSerializer(read_only=True)

    class Meta:
        model = FavoriteProduct
        fields = ['id', 'product', 'created_at']

class ProductVariantSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.product_name", read_only=True)
    category_name = serializers.CharField(source="category.category_name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "parent",
            "parent_name",
            "category",
            "category_name",
            "product_name",
            "product_description",
            "price",
            "quantity",
            "quantity_unit",
            "stock_quantity",
            "is_available",
            "product_image",
        ]
        read_only_fields = ["category"]  # ✅ category auto-assigned

    def validate(self, data):
        parent = data.get("parent")
        if not parent:
            raise serializers.ValidationError("A variant must have a parent product.")
        if parent.parent is not None:
            raise serializers.ValidationError("You cannot create a variant under another variant.")
        return data
    
    def validate_product_name(self, value):
        return normalize_product_name(value)

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Format product name
        product_name = rep.get("product_name")
        if product_name:
            rep["product_name"] = format_name(product_name)

        # Format parent name
        parent_name = rep.get("parent_name")
        if parent_name:
            rep["parent_name"] = format_name(parent_name).title()

        return rep


    def create(self, validated_data):
        parent = validated_data["parent"]
        validated_data["category"] = parent.category  # auto-copy category

        # ✅ If image not provided, inherit from parent
        if not validated_data.get("product_image"):
            if parent.product_image:
                validated_data["product_image"] = parent.product_image

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # ✅ Update category if parent changed
        if instance.parent:
            validated_data["category"] = instance.parent.category

        # ✅ If product_image not provided on update, keep existing
        if not validated_data.get("product_image"):
            if instance.parent and instance.parent.product_image and not instance.product_image:
                validated_data["product_image"] = instance.parent.product_image

        return super().update(instance, validated_data)

class MainProductDropdownSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields =["id","product_name","quantity_unit"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        product_name = rep.get("product_name")
        if product_name:
            rep["product_name"] = format_name(product_name)

        return rep


class ProductFeedbackSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    product_name = serializers.CharField(source="product.product_name", read_only=True)

    class Meta:
        model = ProductFeedback
        fields = [
            "id",
            "product",
            "product_name",
            "user",
            "user_name",
            "rating",
            "comment",
            "is_approved",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "product", "created_at", "updated_at"]

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        product_name = rep.get("product_name")
        if product_name:
            rep["product_name"] = format_name(product_name)

        return rep
    

class NotificationSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.product_name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "type",
            "order_number",
            "product_id",
            "product_name",
            "is_read",
            "created_at",
            "read_at",
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        product_name = rep.get("product_name")
        if product_name:
            rep["product_name"] = format_name(product_name)

        return rep


# serializers.py

