from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for hierarchical categories"""

    list_display = ["get_display_name", "parent", "level", "is_active", "sort_order"]
    list_filter = ["level", "is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}

    def get_display_name(self, obj):
        """Show full path in admin list"""
        return obj.get_display_name()

    get_display_name.short_description = "Full Path"

    fieldsets = (
        ("Category Information", {"fields": ("name", "slug", "parent")}),
        ("Organization", {"fields": ("sort_order",)}),
        ("Status", {"fields": ("is_active",)}),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin interface for products"""

    list_display = ["name", "sku", "category", "price", "stock_quantity", "is_active"]
    list_filter = ["category", "is_active", "created_at"]
    search_fields = ["name", "sku", "description"]

    fieldsets = (
        ("Product Information", {"fields": ("name", "description", "sku")}),
        ("Categorization", {"fields": ("category",)}),
        ("Pricing & Inventory", {"fields": ("price", "stock_quantity")}),
        ("Status", {"fields": ("is_active",)}),
    )
