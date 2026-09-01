from django.contrib import admin
from .models import Product, PurchaseOrder, PurchaseOrderItem, StockMovement, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'email', 'note')
    list_filter = ('store',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'supplier', 'reorder_point', 'order_lot', 'sns_announce', 'is_active')
    list_filter = ('store', 'sns_announce', 'is_active')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'kind', 'quantity', 'at', 'created_by')
    list_filter = ('kind', 'product__store')


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'store', 'status', 'created_at', 'sent_at')
    list_filter = ('store', 'status')
    inlines = [PurchaseOrderItemInline]
