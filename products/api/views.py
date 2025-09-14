from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Avg, Min, Max, Count
from decimal import Decimal

from ..models import Category, Product
from .serializers import (
    CategorySerializer, CategoryTreeSerializer, 
    ProductListSerializer, ProductDetailSerializer,
    CategoryAveragePriceSerializer
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for categories with hierarchy support
    Provides list, retrieve, and custom actions for category trees
    """
    
    queryset = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]  # TODO: Add authentication
    lookup_field = 'slug'
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['parent', 'level']
    search_fields = ['name']
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'tree':
            return CategoryTreeSerializer
        return CategorySerializer
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """
        Get complete category tree starting from root categories.
        Useful for navigation menus and category selection.
        """
        root_categories = self.get_queryset().filter(parent__isnull=True)
        serializer = self.get_serializer(root_categories, many=True)
        return Response({
            'tree': serializer.data,
            'total_categories': self.get_queryset().count()
        })
    
    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        """
        Get all products in this category and its subcategories.
        Supports pagination and filtering.
        """
        category = self.get_object()
        
        # Get products from category and all subcategories
        descendant_categories = [category] + category.get_descendants()
        products = Product.objects.filter(
            category__in=descendant_categories,
            is_active=True
        ).order_by('name')
        
        # Apply pagination
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(products, many=True)
        return Response({
            'category': CategorySerializer(category).data,
            'products': serializer.data,
            'total_products': products.count()
        })
    
    @action(detail=True, methods=['get'])
    def avg_price(self, request, slug=None):
        """
        Calculate average price for products in this category.
        This implements the complex requirement from the project spec.
        """
        category = self.get_object()
        
        # Get all products in category and subcategories
        descendant_categories = [category] + category.get_descendants()
        products = Product.objects.filter(
            category__in=descendant_categories,
            is_active=True
        )
        
        if not products.exists():
            return Response({
                'error': 'No products found in this category',
                'category_id': category.id,
                'category_name': category.name
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate aggregations
        aggregations = products.aggregate(
            average_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price'),
            product_count=Count('id')
        )
        
        # Prepare response data
        response_data = {
            'category_id': category.id,
            'category_name': category.name,
            'average_price': aggregations['average_price'] or Decimal('0.00'),
            'product_count': aggregations['product_count'],
            'includes_subcategories': len(descendant_categories) > 1,
            'min_price': aggregations['min_price'] or Decimal('0.00'),
            'max_price': aggregations['max_price'] or Decimal('0.00'),
        }
        
        serializer = CategoryAveragePriceSerializer(response_data)
        return Response(serializer.data)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for products with filtering and search capabilities.
    Provides list and retrieve actions for product browsing.
    """
    
    queryset = Product.objects.filter(is_active=True).select_related('category')
    permission_classes = [AllowAny]  # Will add authentication later
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'category__parent']
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['name', 'price', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail views"""
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer
    
    def get_queryset(self):
        """Customize queryset with additional filters"""
        queryset = super().get_queryset()
        
        # Filter by availability
        available_only = self.request.query_params.get('available_only')
        if available_only and available_only.lower() == 'true':
            queryset = queryset.filter(stock_quantity__gt=0)
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            try:
                queryset = queryset.filter(price__gte=Decimal(min_price))
            except (ValueError, TypeError):
                pass
        
        if max_price:
            try:
                queryset = queryset.filter(price__lte=Decimal(max_price))
            except (ValueError, TypeError):
                pass
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Get featured products.
        """
        featured_products = self.get_queryset().filter(
            stock_quantity__gte=10
        ).order_by('-created_at')[:8]
        
        serializer = ProductListSerializer(featured_products, many=True)
        return Response({
            'featured_products': serializer.data,
            'count': len(serializer.data)
        })
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """
        Check product availability and stock information
        """
        product = self.get_object()
        
        return Response({
            'product_id': product.id,
            'sku': product.sku,
            'is_available': product.is_in_stock,
            'stock_quantity': product.stock_quantity,
            'price': product.price,
            'last_updated': product.updated_at
        })