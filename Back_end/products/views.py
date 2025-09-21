import json
from django.http import HttpResponse
from django.utils.timezone import now, timedelta
from django.db.models import Sum, Count
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from .models import *
from .serializers import *


class CategoryDetailsView(APIView):
    """
    CRUD API for Category
    """

    def post(self, request):
        """Create a new category"""
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "message": "Category created successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request, pk=None):
        """Get all categories or a single category by ID"""
        if pk:
            category = get_object_or_404(Category, pk=pk)
            serializer = CategorySerializer(category)
            return Response(
                {"status": True, "data": serializer.data}, status=status.HTTP_200_OK
            )

        categories = Category.objects.all().order_by("-created_at")
        serializer = CategorySerializer(categories, many=True)
        return Response(
            {"status": True, "data": serializer.data}, status=status.HTTP_200_OK
        )

    def put(self, request, pk=None):
        """Update category details"""
        if not pk:
            return Response(
                {"status": False, "message": "Category ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category = get_object_or_404(Category, pk=pk)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "message": "Category updated successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk=None):
        """Delete category by ID"""
        if not pk:
            return Response(
                {"status": False, "message": "Category ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category = get_object_or_404(Category, pk=pk)
        category.delete()
        return Response(
            {"status": True, "message": "Category deleted successfully"},
            status=status.HTTP_200_OK,
        )

    

class ProductDetailsView(APIView):
    """
    CRUD API for Category
    """

    def post(self, request):
        """Create a new category"""
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "message": "Product created successfully",
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
            product = get_object_or_404(Product, pk=pk)
            serializer = ProductSerializer(product)
            return Response(
                {"status": True, "data": serializer.data}, status=status.HTTP_200_OK
            )

        categories = Product.objects.all().order_by("-created_at")
        serializer = ProductSerializer(categories, many=True)
        return Response(
            {"status": True, "data": serializer.data}, status=status.HTTP_200_OK
        )

    def put(self, request, pk=None):
        if not pk:
            return Response(
                {"status": False, "message": "Product ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": True,
                    "message": "Product updated successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk=None):
        if not pk:
            return Response(
                {"status": False, "message": "Product ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = get_object_or_404(Product, pk=pk)
        product.delete()
        return Response(
            {"status": True, "message": "Product deleted successfully"},
            status=status.HTTP_200_OK,
        )

class OrderDetailsView(APIView):
    """
    CRUD API for Orders (with items)
    """

    def post(self, request):
        serializer = OrderDetailsSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save()
            return Response(
                {
                    "status": True,
                    "message": "Order created successfully",
                    "data": OrderDetailsSerializer(order).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request, pk=None):
        if pk:
            order = get_object_or_404(OrderDetails, pk=pk)
            serializer = OrderDetailsSerializer(order)
            return Response({"status": True, "data": serializer.data})

        orders = OrderDetails.objects.all()
        serializer = OrderDetailsSerializer(orders, many=True)
        return Response({"status": True, "data": serializer.data})

    def put(self, request, pk=None):
        if not pk:
            return Response({"status": False, "message": "Order ID required"}, status=400)

        order = get_object_or_404(OrderDetails, pk=pk)
        serializer = OrderDetailsSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            order = serializer.save()
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
    """
    Generate PDF invoice for an order using xhtml2pdf
    """
    def get(self, request, order_id):
        # Get the order
        order = get_object_or_404(OrderDetails, id=order_id)

        # Serialize the order (nested items included)
        serializer = OrderDetailsSerializer(order)
        order_data = serializer.data

        # Compute totals (if not already stored)
        subtotal = float(order_data.get("subtotal", 0))
        total_tax = sum(float(item["tax"]) for item in order_data["items"])
        shipping = float(order_data.get("shipping_cost", 0))
        total_amount = float(order_data.get("total_amount", subtotal + total_tax + shipping))

        # Company info
        company = {
            "name": "My Ecommerce Store",
            "address": "123, Anna Nagar, Chennai, Tamil Nadu",
            "email": "support@myecommercestore.com",
            "phone": "+91-9876543210",
            "logo_url": request.build_absolute_uri("/static/image/logoonline.jpg"),
        }

        # Render HTML with template
        html = render_to_string("invoice.html", {
            "order": order_data,   # serialized data
            "company": company,
            "invoice_number": order_data["order_number"],
            "subtotal": subtotal,
            "total_tax": total_tax,
            "shipping": shipping,
            "total_amount": total_amount,
        })

        # Create PDF response
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice_{order_data["order_number"]}.pdf"'

        # Convert HTML to PDF
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse("Error generating PDF", status=500)

        return response