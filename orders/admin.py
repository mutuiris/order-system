from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Inline editing of order items within order admin"""
    model = OrderItem
    extra = 0
    readonly_fields = ['line_total', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': (
                'product', 'quantity', 'unit_price', 'line_total'
            )
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin interface for orders with inline items"""
    
    list_display = [
        'order_number', 'customer', 'status', 'total_amount', 
        'item_count', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'sms_sent', 'email_sent']
    search_fields = ['order_number', 'customer__user__email', 'customer__user__first_name']
    readonly_fields = ['order_number', 'subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']
    
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'status')
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'tax_amount', 'total_amount'),
            'classes': ('collapse',)
        }),
        ('Delivery Information', {
            'fields': ('delivery_address', 'delivery_notes')
        }),
        ('Notifications', {
            'fields': ('sms_sent', 'email_sent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin interface for order items"""
    
    list_display = ['order', 'product_name', 'quantity', 'unit_price', 'line_total']
    list_filter = ['created_at']
    search_fields = ['product_name', 'product_sku', 'order__order_number']
    readonly_fields = ['line_total', 'created_at']