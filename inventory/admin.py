from django.contrib import admin
from .models import InventoryItem, StockRequest

# 1. Customizing how items look in the admin panel
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity')

# 2. Registering our models
admin.site.register(InventoryItem, InventoryItemAdmin)
admin.site.register(StockRequest)