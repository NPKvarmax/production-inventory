from django.contrib import admin
from .models import InventoryItem, StockRequest

class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity')

admin.site.register(InventoryItem, InventoryItemAdmin)
admin.site.register(StockRequest)