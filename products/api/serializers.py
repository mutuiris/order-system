from rest_framework import serializers
from ..models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model with hierarchy support
    Includes parent and children relationships for tree navigation
    """

    # Children categories for tree structure
    children = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = Category
        fields = [
            'id', 'name', 'slug', 'parent', 'parent_name',
            'level', 'sort_order', 'is_active', 'full_path',
            'children', 'product_count', 'created_at'
        ]
        read_only_fields = ['id', 'level', 'created_at']

    def get_children(self, obj):
        """Get immediate children categories"""
        children = obj.children.filter(
            is_active=True).order_by('sort_order', 'name')
        return CategorySerializer(children, many=True, context=self.context).data

    def get_parent_name(self, obj):
        """Get parent category name for display"""
        return obj.parent.name if obj.parent else None

    def get_full_path(self, obj):
        """Get full category path"""
        return obj.get_display_name()

    def get_product_count(self, obj):
        """Get number of active products in the category"""
        return obj.products.filter(is_active=True).count()


class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for category treed
    Used for dropdown menus and navigation
    """

    children = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = Category
        fields = ['id', 'name', 'slug', 'level', 'children']

    def get_children(self, obj):
        """Recursively get all children; include grandchildren at root level"""
        children_qs = obj.children.filter(
            is_active=True).order_by('sort_order', 'name')
        serialized_children = CategoryTreeSerializer(
            children_qs, many=True).data

        flattened = list(serialized_children)
        for child in children_qs:
            gc_qs = child.children.filter(
                is_active=True).order_by('sort_order', 'name')
            if gc_qs.exists():
                flattened.extend(CategoryTreeSerializer(gc_qs, many=True).data)
        return flattened


class ProductListSerializer(serializers.ModelSerializer):
    """
    Serializer for product list view
    """

    category_name = serializers.CharField(
        source='category.name', read_only=True)
    category_path = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = Product
        fields = [
            'id', 'name', 'sku', 'price', 'category_name',
            'category_path', 'stock_quantity', 'is_active',
            'is_available', 'created_at'
        ]

    def get_category_path(self, obj):
        """Get full category path for product"""
        return obj.category.get_display_name()

    def get_is_available(self, obj):
        """Check if product is available for purchase"""
        return obj.is_in_stock


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Detailed product serializer with full information
    Used for product detail view and order creation
    """

    category = CategorySerializer(read_only=True)
    is_available = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = Product
        fields = [
            'id', 'name', 'description', 'sku', 'price',
            'category', 'stock_quantity', 'is_active',
            'is_available', 'related_products', 'created_at', 'updated_at'
        ]

    def get_is_available(self, obj):
        """Check if product is available for purchase"""
        return obj.is_in_stock

    def get_related_products(self, obj):
        """Get other products in the same category"""
        related = Product.objects.filter(
            category=obj.category,
            is_active=True
        ).exclude(id=obj.id)[:4]

        return ProductListSerializer(related, many=True).data


class CategoryAveragePriceSerializer(serializers.Serializer):
    """
    Serializer for category average price endpoint
    """
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    average_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_count = serializers.IntegerField()
    includes_subcategories = serializers.BooleanField()
    price_range = serializers.DictField()

    def to_representation(self, instance):
        """Custom representation for calculated data"""
        return {
            'category_id': instance['category_id'],
            'category_name': instance['category_name'],
            'average_price': str(instance['average_price']),
            'product_count': instance['product_count'],
            'includes_subcategories': instance['includes_subcategories'],
            'price_range': {
                'min_price': str(instance['min_price']),
                'max_price': str(instance['max_price']),
            }
        }
