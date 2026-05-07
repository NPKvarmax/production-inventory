import json
import csv
import openpyxl
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout

from django.http import HttpResponse

from .models import InventoryItem, StockRequest
from .forms import StockRequestForm
from django.utils.timezone import now

@login_required(login_url='login')
def landing_page(request):
    return render(request, 'inventory/landing.html')

@login_required(login_url='login') 
def dashboard(request, item_type):
    
    if item_type not in ['Part', 'Fastener']:
        return redirect('landing')

    items = InventoryItem.objects.filter(item_type=item_type)
    recent_requests = StockRequest.objects.filter(item__item_type=item_type).order_by('-date_requested')
    
    categories = items.values_list('category', flat=True).distinct()
    
    category_filter = request.GET.get('category')
    reorder_filter = request.GET.get('reorder')
    priority_filter = request.GET.get('priority')
    station_filter = request.GET.get('station')

    
    
    if category_filter and category_filter != 'All':
        items = items.filter(category=category_filter)

    if station_filter and station_filter != 'All':
        items = items.filter(station=station_filter)
    
    print("THE BROWSER SENT THIS STATION:", repr(station_filter))
        
    if reorder_filter == 'Yes':
        items = [item for item in items if item.reorder_needed == 'Yes']
    elif reorder_filter == 'No':
        items = [item for item in items if item.reorder_needed == 'No']
        
    if priority_filter and priority_filter != 'All':
        recent_requests = recent_requests.filter(priority=priority_filter)
    recent_requests = recent_requests[:10]

    
    
    total_items_count = len(items) if isinstance(items, list) else items.count()
    low_stock_count = sum(1 for item in items if item.reorder_needed == 'Yes')
    total_inventory_value = sum(item.total_value for item in items)

    chart_labels = json.dumps([item.name for item in items])
    chart_data = json.dumps([float(item.quantity) for item in items]) 

    if request.method == 'POST':
        form = StockRequestForm(request.POST, item_type=item_type)
        if form.is_valid():
            stock_request = form.save(commit=False)
            requested_item = stock_request.item
            requested_qty = stock_request.quantity_requested
            
            if requested_qty <= requested_item.quantity:
                requested_item.quantity -= requested_qty
                requested_item.save() 
                stock_request.requester = request.user
                stock_request.save()
                messages.success(request, f"Successfully requested {requested_qty} of {requested_item.name}.")
                return redirect('dashboard', item_type=item_type) 
            else:
                messages.error(request, f"Error: You requested {requested_qty}, but only {requested_item.quantity} are available.")
    else:
        form = StockRequestForm(item_type=item_type) 

    if isinstance(items, list):
        item_ids = [item.id for item in items]
        form.fields['item'].queryset = InventoryItem.objects.filter(id__in=item_ids)
    else:
        form.fields['item'].queryset = items
    
    context = {
        'item_type': item_type, 
        'items': items,
        'form': form,
        'recent_requests': recent_requests,
        'categories': categories,
        'total_items_count': total_items_count,
        'low_stock_count': low_stock_count,
        'total_inventory_value': total_inventory_value,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }
    return render(request, 'inventory/dashboard.html', context)

def login_page(request):
    if request.user.is_authenticated:
        return redirect('landing')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('landing') 
    else:
        form = AuthenticationForm()

    context = {'form': form}
    return render(request, 'inventory/login.html', context)

def logout_user(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def export_inventory_csv(request):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied: Only administrators can download reports.")
        return redirect('landing')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="complete_inventory_status.csv"'

    writer = csv.writer(response)
    writer.writerow(['Type', 'Item Name', 'Current Quantity', 'Status']) # Added Type

    items = InventoryItem.objects.all()
    for item in items:
        status = 'LOW STOCK' if item.quantity < 10 else 'OK'
        writer.writerow([item.item_type, item.name, item.quantity, status])

    return response

@login_required(login_url='login')
def executive_report(request):
    # SECURITY: Kick out anyone who isn't a manager
    if not request.user.is_superuser:
        messages.error(request, "Access Denied: Executive reporting only.")
        return redirect('landing')

    all_items = InventoryItem.objects.all()
    
    # High-Level Metrics (Replaces manual spreadsheet math)
    total_units = sum(item.quantity for item in all_items)
    total_value = sum(item.total_value for item in all_items if hasattr(item, 'total_value')) 

    # Risk Detection (Finds items like your Cable Ties that hit 0)
    critical_items = InventoryItem.objects.filter(quantity__lte=0)

    # Monthly Consumption Math
    current_year = now().year
    current_month = now().month
    
    monthly_requests = StockRequest.objects.filter(
        date_requested__year=current_year,
        date_requested__month=current_month
    )
    
    total_parts_consumed = sum(req.quantity_requested for req in monthly_requests)
    total_requests_count = monthly_requests.count()

    context = {
        'total_value': total_value,
        'total_units': total_units,
        'critical_items': critical_items,
        'total_parts_consumed': total_parts_consumed,
        'total_requests_count': total_requests_count,
        'current_month_name': now().strftime("%B %Y"),
    }
    return render(request, 'inventory/executive_report.html', context)

@login_required(login_url='login')
def export_excel_report(request):
    if not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('landing')

    #Creating a blank Excel Workbook
    wb = openpyxl.Workbook()
    
    # OVERVIEW TAB 
    ws1 = wb.active
    ws1.title = "Inventory Overview"
    ws1.append(["Company", "Wahu Mobility"])
    ws1.append(["Report Date", datetime.now().strftime("%Y-%m-%d")])
    ws1.append([]) 
    
    ws1.append(["Item Name", "Category", "Station", "Quantity", "Total Value"])
    items = InventoryItem.objects.all()
    for item in items:
        val = item.total_value if hasattr(item, 'total_value') else 0 
        ws1.append([item.name, item.category, item.station, item.quantity, val])

    #MONTHLY CONSUMPTION TAB 
    ws2 = wb.create_sheet(title="Monthly Consumption")
    ws2.append(["Date Requested", "Item Name", "Quantity Pulled", "Requester"])
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    monthly_requests = StockRequest.objects.filter(
        date_requested__year=current_year, 
        date_requested__month=current_month
    )
    for req in monthly_requests:
        ws2.append([
            req.date_requested.strftime("%Y-%m-%d"), 
            req.item.name, 
            req.quantity_requested, 
            req.requester.username
        ])

    # URGENT ACTIONS (0 Stock) TAB
    ws3 = wb.create_sheet(title="Urgent Actions")
    ws3.append(["URGENT RESTOCK REQUIRED"])
    ws3.append(["Item Name", "Station", "Last Known Quantity"])
    
    critical_items = InventoryItem.objects.filter(quantity__lte=0)
    for item in critical_items:
        ws3.append([item.name, item.station, item.quantity])

    # Pushing to the browser as a download!
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Wahu_Inventory_Report_{datetime.now().strftime("%b_%Y")}.xlsx"'
    
    wb.save(response)
    return response