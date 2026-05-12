import openpyxl
from django.http import HttpResponse
from django.contrib import admin
from .models import InventoryItem, StockRequest, BuildKit, KitItem

@admin.action(description='Download Selected Logs to Excel')
def export_requests_to_excel(modeladmin, request, queryset):
    # receiving  Excel file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Wahu_All_Stock_Requests.xlsx"'
    
    # Excel file Builder
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Audit Logs"
    
    ws.append(["Date Requested", "Item Name", "Quantity Pulled", "Requester"])
    #Adding the data to the Excel file
    for req in queryset:
        ws.append([
            req.date_requested.strftime("%Y-%m-%d %H:%M"), 
            req.item.name, 
            req.quantity_requested, 
            req.requester.username
        ])
    # Saving the Excel file
    wb.save(response)
    return response

#The Undo Action
@admin.action(description='UNDO: Restore items to inventory and delete log')
def revert_stock_requests(modeladmin, request, queryset):
    for stock_request in queryset:
        item = stock_request.item # Get the original item
        item.quantity += stock_request.quantity_requested # Add the quantity BACK to the main inventory balance
        item.save()
        stock_request.delete()# Delete the log so it doesn't permanently ruin audit


#  Inventory list
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'station', 'quantity')
    search_fields = ('name', 'station')
    list_filter = ('station', 'category')

# Stock Request Logs
class StockRequestAdmin(admin.ModelAdmin):
    list_display = ('item', 'quantity_requested', 'requester', 'date_requested')
    search_fields = ('item__name', 'requester__username')
    list_filter = ('date_requested', 'requester')
    date_hierarchy = 'date_requested'
    actions = [export_requests_to_excel, revert_stock_requests]

#BuildKit setup

class KitItemInline(admin.TabularInline):
    model = KitItem
    extra = 3 

class BuildKitAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    inlines = [KitItemInline]



admin.site.register(InventoryItem, InventoryItemAdmin)
admin.site.register(StockRequest, StockRequestAdmin)
admin.site.register(BuildKit, BuildKitAdmin)