import json
from django.http import HttpResponse
from num2words import num2words
from django.utils.timezone import now, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from collections import OrderedDict
from rest_framework import status,generics
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from django.db.models import DecimalField,Sum, F,ExpressionWrapper
from Back_end.pagination import CustomPageNumberPagination
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from .models import *
from .serializers import *
from django.utils import timezone
from django.db.models.functions import TruncDate,Coalesce,Cast
from django.db.models import Prefetch, Q
from payment.models import GSTSetting
from .utils import amount_in_words_indian,link_callback
import os
from xhtml2pdf import default
from django.conf import settings
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from xhtml2pdf.default import DEFAULT_FONT

def normalize_category_name(name: str):

    return name.strip().lower().replace(" ", "_")

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

class ProductSetPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 100


class CategoryDetailsView(APIView):

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            # Check uniqueness ignoring case
            normalized_name = serializer.validated_data["category_name"]
            if Category.objects.filter(category_name__iexact=normalized_name).exists():
                return Response(
                    {"status": False, "message": "Category with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer.save()
            return Response(
                {"status": True, "message": "Category created successfully", "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, pk=None):
        if pk:
            category = get_object_or_404(Category, pk=pk)
            serializer = CategorySerializer(category)
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
        categories = Category.objects.all().order_by("-created_at")
        serializer = CategorySerializer(categories, many=True)
        return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def put(self, request, pk=None):
        if not pk:
            return Response({"status": False, "message": "Category ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        category = get_object_or_404(Category, pk=pk)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            normalized_name = serializer.validated_data.get("category_name")
            if normalized_name and Category.objects.filter(category_name__iexact=normalized_name).exclude(pk=pk).exists():
                return Response(
                    {"status": False, "message": "Category with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer.save()
            return Response({"status": True, "message": "Category updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response({"status": False, "message": "Category ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        category = get_object_or_404(Category, pk=pk)
        category.delete()
        return Response({"status": True, "message": "Category deleted successfully"}, status=status.HTTP_200_OK)


class ProductDetailsView(APIView):

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            product_name = serializer.validated_data.get("product_name")

            # ✅ Unique check (case-insensitive)
            if Product.objects.filter(product_name__iexact=product_name).exists():
                return Response(
                    {"status": False, "message": "Product with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer.save()
            return Response(
                {"status": True, "message": "Product created successfully", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )

        # ✅ Return validation errors
        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    pagination_class = StandardResultsSetPagination

    def get(self, request, pk=None):
        try:
            if pk:
                product = get_object_or_404(Product, pk=pk)
                serializer = ProductSerializer(product)
                return Response(
                    {"status": True, "data": serializer.data},
                    status=status.HTTP_200_OK,
                )

            products = Product.objects.filter(parent__isnull=True).order_by("-created_at")
            serializer = ProductSerializer(products, many=True)

            return Response(
                {"status": True, "data": serializer.data},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"status": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk=None):
        if not pk:
            return Response({"status": False, "message": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            product_name = serializer.validated_data.get("product_name")

            # ✅ Unique check excluding current product
            if product_name and Product.objects.filter(product_name__iexact=product_name).exclude(pk=pk).exists():
                return Response(
                    {"status": False, "message": "Product with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer.save()
            return Response({"status": True, "message": "Product updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not pk:
            return Response({"status": False, "message": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, pk=pk)
        product.delete()
        return Response({"status": True, "message": "Product deleted successfully"}, status=status.HTTP_200_OK)

class OrderPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class OrderDetailsView(generics.GenericAPIView):
    """
    CRUD API for Orders (with pagination)
    """

    serializer_class = OrderDetailsSerializer
    pagination_class = OrderPagination

    def get_queryset(self):
        return OrderDetails.objects.all().order_by("-created_at")

    def get(self, request, pk=None):
        if pk:
            order = get_object_or_404(OrderDetails, pk=pk)
            serializer = self.get_serializer(order)
            return Response({"status": True, "data": serializer.data})

        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({"status": True, "data": serializer.data})

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save()
            return Response(
                {
                    "status": True,
                    "message": "Order created successfully",
                    "data": self.get_serializer(order).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request, pk=None):
        if not pk:
            return Response({"status": False, "message": "Order ID required"}, status=400)

        order = get_object_or_404(OrderDetails, pk=pk)
        serializer = self.get_serializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": True, "message": "Order updated", "data": serializer.data},
                status=200,
            )
        return Response({"status": False, "errors": serializer.errors}, status=400)

    def delete(self, request, pk=None):
        if not pk:
            return Response({"status": False, "message": "Order ID required"}, status=400)

        order = get_object_or_404(OrderDetails, pk=pk)
        order.delete()
        return Response({"status": True, "message": "Order deleted"}, status=200)
    
class InvoicePDFView(APIView):
    def get(self, request, order_id):
        # Get order and invoice
        order = get_object_or_404(OrderDetails, id=order_id)
        invoice, _ = Invoice.objects.get_or_create(order=order)

        # GST + totals
        gst_setting = GSTSetting.objects.first()
        gst_percentage = gst_setting.gst_percentage if gst_setting else Decimal("18.00")

        subtotal = sum(float(item.price) * item.quantity for item in order.items.all())
        gst_amount = subtotal * float(gst_percentage) / 100
        shipping = float(order.shipping_cost or 0)
        total_amount = subtotal + gst_amount + shipping

        amount_in_words = amount_in_words_indian(total_amount)

        # Paths
        logo_path = os.path.join(settings.BASE_DIR, "static", "image", "Logo.jpeg")
        font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "DejaVuSans.ttf")

        # ✅ Register and embed DejaVuSans font
        pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
        registerFontFamily(
            "DejaVuSans",
            normal="DejaVuSans",
            bold="DejaVuSans",
            italic="DejaVuSans",
            boldItalic="DejaVuSans",
        )

        # ✅ Replace default Helvetica with DejaVuSans (fixes ₹ everywhere)
        default.DEFAULT_FONT["helvetica"] = "DejaVuSans"
        default.DEFAULT_FONT["Times-Roman"] = "DejaVuSans"
        default.DEFAULT_FONT["Courier"] = "DejaVuSans"
        default.DEFAULT_FONT["Helvetica"] = "DejaVuSans"
        default.DEFAULT_FONT["Helvetica-Bold"] = "DejaVuSans"
        default.DEFAULT_FONT["Helvetica-Oblique"] = "DejaVuSans"
        default.DEFAULT_FONT["Helvetica-BoldOblique"] = "DejaVuSans"

        # Company Info
        company = {
            "name": "Vallalar Naturals from Village Kannama",
            "address": "No. 2, South Street, Abatharanapuram, Serakuppam Post, Vadalur - 607303.",
            "email": "vallalarnaturalsvillagekannama@gmail.com",
            "phone": "+91 7639157615",
            "gstin": "33FEHPS4088N1ZP",
            "logo_path": logo_path,
            "font_path": font_path,
        }

        # Render HTML
        html = render_to_string("invoice.html", {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.generated_at.strftime("%d-%b-%Y"),
            "order": order,
            "customer": {
                "name": f"{order.first_name or ''} {order.last_name or ''}".strip(),
                "address": order.shipping_address,
                "contact": order.contact_number,
            },
            "company": company,
            "subtotal": f"{subtotal:.2f}",
            "gst_percentage": gst_percentage,
            "gst_amount": f"{gst_amount:.2f}",
            "shipping": f"{shipping:.2f}",
            "total_amount": f"{total_amount:.2f}",
            "amount_in_words": amount_in_words,
            "payment_method": order.payment_method,
        })

        # Step 1: Generate base PDF in memory
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(
            html, dest=pdf_buffer, link_callback=link_callback, encoding="UTF-8"
        )

        if pisa_status.err:
            return HttpResponse("Error generating PDF", status=500)

        pdf_buffer.seek(0)
        reader = PdfReader(pdf_buffer)
        writer = PdfWriter()

        # Step 2: Apply watermark background (transparent)
        for page in reader.pages:
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=(595.27, 841.89))  # A4 size
            width, height = 595.27, 841.89

            can.saveState()
            logo = ImageReader(logo_path)
            can.setFillAlpha(0.08)  # Transparency (0.0 - 1.0)

            # Adjust background size/position
            img_width = width * 0.9
            img_height = img_width * 1.0
            x = (width - img_width) / 2
            y = (height - img_height) / 2

            can.drawImage(logo, x, y, width=img_width, height=img_height, mask="auto")
            can.restoreState()
            can.save()

            packet.seek(0)
            watermark_pdf = PdfReader(packet)
            watermark_page = watermark_pdf.pages[0]
            page.merge_page(watermark_page)
            writer.add_page(page)

        # Step 3: Return final merged PDF
        final_output = BytesIO()
        writer.write(final_output)
        final_output.seek(0)

        response = HttpResponse(final_output, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        )
        return response
    
class ProductListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, id=None):
        offer_only = request.query_params.get("offer_only", "false").lower() == "true"

        # --- 1️⃣ Single Product by ID ---
        if id:
            try:
                product = Product.objects.get(pk=id)
            except Product.DoesNotExist:
                return Response({
                    "success": False,
                    "message": "Product not found",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = ProductWithOfferSerializer(product)
            return Response({
                "success": True,
                "message": "Product fetched successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        # --- 2️⃣ Multiple Products (no pagination) ---
        qs = Product.objects.filter(parent__isnull=True).select_related("category").prefetch_related(
            "offers",
            Prefetch("variants", queryset=Product.objects.filter(is_available=True, stock_quantity__gt=0))
        )

        # Apply offer_only filter if requested
        if offer_only:
            qs = qs.filter(
                Q(offers__is_active=True) |
                Q(variants__offers__is_active=True)
            ).distinct()

        # --- 3️⃣ Serialize all products (no pagination) ---
        serializer = ProductWithOfferSerializer(qs.order_by("-created_at"), many=True)

        # --- 4️⃣ Response ---
        return Response({
            "success": True,
            "message": "Products fetched successfully",
            "total_items": qs.count(),
            "data": serializer.data
        }, status=status.HTTP_200_OK)
        
class CategoryListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, id=None):
        try:
            if id:
                category = Category.objects.filter(id=id).first()
                if not category:
                    return Response({
                        "message": "Category not found",
                        "success": False,
                        "error": True,
                        "data": None
                    }, status=status.HTTP_404_NOT_FOUND)

                serializer = CategorySerializer(category)
                return Response({
                    "message": "Category fetched successfully",
                    "status": True,
                    "data": serializer.data
                }, status=status.HTTP_200_OK)

            else:
                categories = Category.objects.all().order_by("-created_at")
                serializer = CategorySerializer(categories, many=True)
                return Response(
                    {"status": True, "data": serializer.data}, status=status.HTTP_200_OK
                )
        except Exception as e:
            return Response({
                "message": str(e),  # 
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ProductFilter(APIView):
    permission_classes = [AllowAny]

    def get(self, request, category_id=None):
        try:
            # ✅ Only fetch main products (those without a parent)
            products = Product.objects.filter(parent__isnull=True).order_by("-id")

            # ✅ Filter by category if provided
            if category_id:
                products = products.filter(category_id=category_id)

            # ✅ Apply pagination
            paginator = CustomPageNumberPagination()
            paginated_qs = paginator.paginate_queryset(products, request)
            serializer = ProductWithOfferSerializer(paginated_qs, many=True)

            # ✅ Return paginated response
            return paginator.get_paginated_response(serializer.data)

        except Exception as e:
            return Response({
                "message": str(e),
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactusView(APIView):

    def post(self, request):
        serializer = ContactusSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "message": "Contactus created successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request, pk=None):

        if pk:
            contactus = get_object_or_404(Contactus, pk=pk)
            serializer = ContactusSerializer(contactus)
            return Response(
                {"status": True, "data": serializer.data}, status=status.HTTP_200_OK
            )

        contactus = Contactus.objects.all().order_by("-created_at")
        
        paginator = CustomPageNumberPagination()
        paginated_qs = paginator.paginate_queryset(contactus, request)
        serializer = ContactusSerializer(paginated_qs, many=True)

        return paginator.get_paginated_response(serializer.data)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import OrderDetails

class OrderStatusUpdateView(APIView):

    def put(self, request, id):
        try:
            order = OrderDetails.objects.get(id=id)
        except OrderDetails.DoesNotExist:
            return Response(
                {"message": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        order_status = request.data.get("order_status")
        courier_number = request.data.get("courier_number")

        # --- Validation ---
        if not order_status:
            return Response(
                {"message": "Missing field: order_status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_statuses = [choice[0] for choice in OrderDetails.OrderStatus.choices]
        if order_status not in valid_statuses:
            return Response(
                {"message": f"Invalid status. Allowed values: {valid_statuses}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Require courier number if status = shipped ---
        if order_status == OrderDetails.OrderStatus.SHIPPED and not courier_number:
            return Response(
                {"message": "courier_number is required when status is 'shipped'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Update order ---
        order.status = order_status

        if courier_number:
            order.courier_number = courier_number

        order.save()

        response_data = {
            "message": "Order status updated successfully.",
            "order_id": order.id,
            "order_number": order.order_number,
            "order_status": order.status,
        }

        # Include courier details if shipped
        if order.status == OrderDetails.OrderStatus.SHIPPED:
            response_data["courier_number"] = order.courier_number
            response_data["preferred_courier_service"] = order.preferred_courier_service

        return Response(response_data, status=status.HTTP_200_OK)


class OfferPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class OfferDetailsView(APIView):

    def get(self, request, pk=None):
        today = timezone.now().date()

        # ✅ Deactivate expired offers
        OfferDetails.objects.filter(end_date__lt=today, is_active=True).update(is_active=False)

        # ✅ Activate offers that are now valid (current date within range)
        OfferDetails.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_active=False,
        ).update(is_active=True)

        if pk:
            offer = get_object_or_404(OfferDetails, pk=pk)
            serializer = OfferDetailsSerializer(offer)
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)

        # ✅ Paginate all offers (newest first)
        offers = OfferDetails.objects.all().order_by('-created_at')
        paginator = OfferPagination()
        result_page = paginator.paginate_queryset(offers, request)
        serializer = OfferDetailsSerializer(result_page, many=True)

        return paginator.get_paginated_response({
            "status": True,
            "message": "Offers retrieved successfully.",
            "data": serializer.data,
        })

    def post(self, request):
        data = request.data

        # ✅ Accept both single object and list of objects
        if isinstance(data, list):
            serializer = OfferDetailsSerializer(data=data, many=True)
        else:
            serializer = OfferDetailsSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": True,
                "message": "Offer(s) created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        offer = get_object_or_404(OfferDetails, pk=pk)
        serializer = OfferDetailsSerializer(offer, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": True,
                "message": "Offer updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        offer = get_object_or_404(OfferDetails, pk=pk)
        serializer = OfferDetailsSerializer(offer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": True,
                "message": "Offer partially updated",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        offer = get_object_or_404(OfferDetails, pk=pk)
        try:
            offer.delete()
            return Response({"status": True, "message": "Offer deleted successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": False,
                "message": f"Failed to delete offer: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   
        
# views.py
class ProductsByCategory(APIView):
    def get(self, request, category_id):
        try:
            today = timezone.now().date()

            # ✅ Get IDs of products with currently active offers
            active_offer_product_ids = OfferDetails.objects.filter(
                category_id=category_id,
                is_active=True,
                start_date__lte=today,
                end_date__gte=today,
            ).values_list("product_id", flat=True)

            # ✅ Filter products in this category WITHOUT active offers
            products = (
                Product.objects.filter(category_id=category_id)
                .exclude(id__in=active_offer_product_ids)
                .only("id", "product_name", "category__category_name")
            )

            if not products.exists():
                return Response(
                    {
                        "status": False,
                        "message": "No available products without active offers in this category.",
                        "data": [],
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = FillterProductSerializer(products, many=True)
            return Response(
                {
                    "status": True,
                    "message": "Products retrieved successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "status": False,
                    "message": f"Something went wrong: {str(e)}",
                    "data": [],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class DashboardAPIView(APIView):

    def get(self, request):
        try:
            now = timezone.now()  # timezone-aware
            last_7_days = now - timedelta(days=6)

            # ---------------- Stats ----------------
            total_sales = OrderDetails.objects.filter(payment_status__iexact="success")\
                .aggregate(total=Coalesce(Sum("total_amount"), Decimal("0.00"), output_field=DecimalField(max_digits=20, decimal_places=2)))["total"]

            stats = {
                "total_sales": total_sales,
                "total_orders": OrderDetails.objects.count(),
                "total_customers": CustomerDetails.objects.count(),
                "total_products": Product.objects.count(),
                "confirmed_orders": OrderDetails.objects.filter(status__iexact="order_confirmed").count(),
                "cancelled_orders": OrderDetails.objects.filter(status__iexact="cancelled").count(),
            }

            # ---------------- Sales Chart (last 7 days) ----------------
            sales_qs = (
                OrderDetails.objects.filter(payment_status__iexact="success", ordered_at__date__gte=last_7_days.date())
                .annotate(date=TruncDate("ordered_at"))
                .values("date")
                .annotate(
                    sales=Coalesce(
                        Sum("total_amount"), 
                        Decimal("0.00"), 
                        output_field=DecimalField(max_digits=20, decimal_places=2)
                    )
                )
                .order_by("date")
            )

            # Fill missing days with 0
            sales_chart_dict = OrderedDict()
            for i in range(7):
                day = (now - timedelta(days=6 - i)).date()
                sales_chart_dict[day] = Decimal("0.00")

            for sale in sales_qs:
                sales_chart_dict[sale["date"]] = sale["sales"]

            sales_chart = [{"date": d, "sales": s} for d, s in sales_chart_dict.items()]

            # ---------------- Top Products ----------------
            top_products_qs = (
                OrderItem.objects.filter(order__payment_status__iexact="success")
                .values("product_id", "product__product_name")
                .annotate(
                    total_sold=Coalesce(Sum("quantity"), 0),
                    total_revenue=Coalesce(Sum(F("quantity") * F("price"), output_field=DecimalField(max_digits=20, decimal_places=2)), Decimal("0.00"))
                )
                .order_by("-total_sold")[:5]
            )

            # ---------------- Recent Orders ----------------
            recent_orders_qs = (
                OrderDetails.objects.select_related("customer", "customer__auth")
                .only(
                    "order_number",
                    "total_amount",
                    "status",
                    "ordered_at",
                    "customer__full_name",
                    "customer__auth__email",
                )
                .order_by("-ordered_at")[:5]
            )

            # ---------------- Low Stock Products ----------------
            low_stock_qs = (
                                Product.objects
                                .filter(stock_quantity__lte=5)
                                .select_related("category")  
                                .only("id", "product_name", "stock_quantity", "category__category_name")
                                .order_by("stock_quantity")[:5]
                            )


            # ---------------- New Customers (last 7 days) ----------------
            new_customers_qs = (
                CustomerDetails.objects.select_related("auth")
                .filter(auth__created_at__gte=last_7_days)
                .order_by("-auth__created_at")[:5]
            )

            # ---------------- Serialize ----------------
            data = {
                "stats": DashboardStatsSerializer(stats).data,
                "sales_chart": SalesChartSerializer(sales_chart, many=True).data,
                "top_products": TopProductSerializer(top_products_qs, many=True).data,
                "recent_orders": RecentOrderSerializer(recent_orders_qs, many=True).data,
                "low_stock_products": LowStockProductSerializer(low_stock_qs, many=True).data,
                "new_customers": NewCustomerSerializer(new_customers_qs, many=True).data,
            }

            return Response({
                "status": True,
                "message": "Dashboard data fetched successfully",
                "data": data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": False,
                "message": f"Something went wrong: {str(e)}",
                "data": {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class StockAvailability(APIView):
    def get(self, request):
        product_id = request.GET.get("product_id")

        if not product_id:
            return Response({
                "status": False,
                "message": "product_id is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
            return Response({
                "status": True,
                "product_id": product_id,
                "stock": product.stock_quantity  # change to your stock field name
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "status": False,
                "message": "Product not found"
            }, status=status.HTTP_404_NOT_FOUND)
        

class FavoriteToggleView(APIView):

    def post(self, request):
        product_id = request.data.get("product_id")
        auth_id = request.data.get("auth_id")
        if not product_id:
            return Response({"error": "product_id required"}, status=400)

        # Get logged in customer
        customer = CustomerDetails.objects.get(auth_id=auth_id)

        # Check if favorite exists
        favorite = FavoriteProduct.objects.filter(product_id=product_id, customer=customer).first()

        if favorite:
            favorite.delete()
            return Response({"message": "Removed from favorites", "is_favorite": False})

        # Create favorite
        FavoriteProduct.objects.create(product_id=product_id, customer=customer)
        return Response({"message": "Added to favorites", "is_favorite": True})

class FavoriteListView(APIView):
    pagination_class = ProductSetPagination

    def get(self, request):
        auth_id = request.GET.get("auth_id")
        customer = CustomerDetails.objects.get(auth_id=auth_id)

        # Get favorite product IDs
        favorites = FavoriteProduct.objects.filter(customer=customer).order_by("-created_at")
        product_ids = favorites.values_list("product_id", flat=True)

        # Fetch actual product objects
        products = Product.objects.filter(id__in=product_ids).order_by("-created_at")

        paginator = self.pagination_class()
        paginated_products = paginator.paginate_queryset(products, request)

        serializer = ProductWithOfferSerializer(paginated_products, many=True)

        return Response({
            "success": True,
            "message": "Favorite products fetched successfully",
            "total_items": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "data": serializer.data
        }, status=status.HTTP_200_OK)

class FavoriteListIdsView(APIView):
    def get(self, request):
        auth_id = request.query_params.get("auth_id")

        if not auth_id:
            return Response({"error": "auth_id required"}, status=400)

        try:
            customer = CustomerDetails.objects.get(auth_id=auth_id)
        except CustomerDetails.DoesNotExist:
            return Response({"favorites": []})  

        fav_ids = FavoriteProduct.objects.filter(customer=customer).values_list("product_id", flat=True)

        return Response({"favorites": list(fav_ids)})


class ProductVariant(APIView):

    def post(self, request):
        parent_id = request.data.get("parent")
        serializer = ProductVariantSerializer(data=request.data)
        if serializer.is_valid():
            if parent_id:
                parent = get_object_or_404(Product, id=parent_id)
                serializer.validated_data["category"] = parent.category  
            product = serializer.save()
            return Response({
                "status": True,
                "message": "Variant created successfully" if parent_id else "Product created successfully",
                "data": ProductVariantSerializer(product).data
            }, status=status.HTTP_201_CREATED)
        return Response({"status": False, "errors": serializer.errors}, status=400)
    
    def get(self, request, pk=None):
            # ✅ If single variant (by ID)
            if pk:
                product = get_object_or_404(Product, pk=pk)
                serializer = ProductVariantSerializer(product)
                return Response(
                    {"status": True, "data": serializer.data},
                    status=status.HTTP_200_OK,
                )

            # ✅ If list of all variants (paginated)
            products = Product.objects.filter(parent__isnull=False).order_by("-created_at")

            paginator = PageNumberPagination()
            paginator.page_size = int(request.GET.get("page_size", 10))  # default 10 items per page
            paginated_products = paginator.paginate_queryset(products, request)

            serializer = ProductVariantSerializer(paginated_products, many=True)
            return paginator.get_paginated_response({
                "status": True,
                "data": serializer.data
            })
    
    def put(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductVariantSerializer(product, data=request.data, partial=True)

        if serializer.is_valid():
            parent = serializer.validated_data.get("parent") or product.parent
            if parent:
                serializer.validated_data["category"] = parent.category

            updated_product = serializer.save()
            return Response({
                "status": True,
                "message": "Product updated successfully",
                "data": ProductVariantSerializer(updated_product).data
            }, status=status.HTTP_200_OK)

        return Response({
            "status": False,
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    
    def delete(self, request, pk):
        product = self.get_object(pk)
        product.delete()
        return Response({
            "status": True,
            "message": "Product deleted successfully"
        }, status=200)
    
class ProductVariantFillter(APIView):
    def get(self, request):
        parent_id = request.query_params.get("parent_id")

        if not parent_id:
            return Response({
                "status": False,
                "message": "parent_id query parameter is required."
            }, status=400)

        # ✅ Get product (can be parent or variant)
        product = get_object_or_404(Product, id=parent_id)

        # ✅ If product is a VARIANT, get its parent
        if product.parent:
            parent = product.parent
        else:
            parent = product

        # ✅ Get all variants under that parent
        variants = parent.variants.all().order_by("-created_at")

        # ✅ Serialize both parent and variants
        parent_serializer = ProductVariantSerializer(parent)
        variant_serializer = ProductVariantSerializer(variants, many=True)

        # ✅ Combine results (parent first, then variants)
        all_items = [parent_serializer.data] + variant_serializer.data

        return Response({
            "status": True,
            "parent_id": parent.id,
            "parent_name": parent.product_name,
            "total_variants": variants.count(),
            "data": all_items
        }, status=200)

class MainProductDropdown(APIView):
    def get(self, request):

        main_products = Product.objects.filter(parent__isnull=True).order_by("-created_at")
        serializer = MainProductDropdownSerializer(main_products, many=True)
        return Response(
            {"status": True, "data": serializer.data},
            status=status.HTTP_200_OK,
        )


class ProductFeedbackAPIView(APIView):


    def get_customer(self, user):
        """Return CustomerDetails linked to the logged-in Auth user."""
        try:
            return user.customer_details
        except CustomerDetails.DoesNotExist:
            return None

    def get(self, request, product_id):
        """✅ Fetch feedback for this user and product"""
        customer = self.get_customer(request.user)
        if not customer:
            return Response({
                "status": False,
                "message": "Customer profile not found."
            }, status=status.HTTP_400_BAD_REQUEST)

        feedback = ProductFeedback.objects.filter(product_id=product_id, user=customer).first()
        if not feedback:
            return Response({
                "status": False,
                "message": "No feedback found for this user.",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductFeedbackSerializer(feedback)
        return Response({
            "status": True,
            "message": "Feedback fetched successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request, product_id):
        """✅ Create or update feedback for the logged-in customer"""
        product = get_object_or_404(Product, id=product_id)
        customer = self.get_customer(request.user)

        if not customer:
            return Response({
                "status": False,
                "message": "Customer profile not found."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if feedback already exists
        feedback = ProductFeedback.objects.filter(product=product, user=customer).first()

        if feedback:
            # Update existing feedback
            serializer = ProductFeedbackSerializer(feedback, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "status": True,
                    "message": "Feedback updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response({
                "status": False,
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create new feedback
        serializer = ProductFeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(product=product, user=customer)
            return Response({
                "status": True,
                "message": "Feedback added successfully.",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "status": False,
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    

class FeedbackPagination(PageNumberPagination):
    page_size = 5  # 5 reviews per page
    page_size_query_param = 'page_size'
    max_page_size = 20


class ProductFeedbackListAPIView(APIView):
    """📄 Paginated reviews for a product"""
    pagination_class = FeedbackPagination

    def get(self, request, product_id):
        feedbacks = ProductFeedback.objects.filter(product_id=product_id).order_by('-created_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(feedbacks, request)
        serializer = ProductFeedbackSerializer(page, many=True)
        return paginator.get_paginated_response({
            "status": True,
            "message": "Reviews fetched successfully",
            "data": serializer.data
        })
    
class GlobalOrderSearchView(generics.ListAPIView):
    serializer_class = OrderDetailsSerializer

    def get_queryset(self):
        queryset = OrderDetails.objects.all().select_related("customer").prefetch_related("items")

        # ✅ Search by Order ID only
        order_id = self.request.query_params.get("order_id")
        if order_id:
            return queryset.filter(order_number__icontains=order_id)

        # ✅ Global search
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(preferred_courier_service__icontains=search)
                | Q(courier_number__icontains=search)
                | Q(payment_status__icontains=search)
                | Q(status__icontains=search)
                | Q(total_amount__icontains=search)
            )

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class GlobalProductSearchView(generics.ListAPIView):

    permission_classes = [AllowAny]

    serializer_class = ProductWithOfferSerializer

    def get_queryset(self):
        queryset = Product.objects.all().select_related("category")

        # ✅ Global search
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(product_name__icontains=search)
                | Q(product_description__icontains=search)
                | Q(category__category_name__icontains=search)
            )

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class CustomerNotifications(APIView):
    def get(self, request, customer_id):
        # Only show unread notifications
        notifications = Notification.objects.filter(
            customer_id=customer_id,
            is_read=False
        )

        serializer = NotificationSerializer(notifications, many=True)

        return Response({
            "success": True,
            "total": notifications.count(),
            "data": serializer.data
        })


class MarkNotificationRead(APIView):
    def put(self, request, id):
        try:
            notification = Notification.objects.get(id=id)
            notification.mark_as_read()
            return Response({"success": True, "message": "Notification marked as read"})
        except Notification.DoesNotExist:
            return Response({"success": False, "message": "Notification not found"}, status=404)
