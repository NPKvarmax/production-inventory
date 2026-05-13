from django.db.models import Sum, Count
import json
import csv
import openpyxl
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import InventoryItem, StockRequest, BuildKit
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout

from django.http import HttpResponse
from django.utils.timezone import now
from .models import InventoryItem, StockRequest
from .forms import StockRequestForm

@login_required(login_url='login')
def landing_page(request):
    return render(request, 'inventory/landing.html')

@login_required(login_url='login') 
def dashboard(request, item_type):
    
    if item_type not in ['Part', 'Fastener']:
        return redirect('landing')

    items = InventoryItem.objects.filter(item_type=item_type)
    #RECENT OPERATIONS LOG
    if request.user.is_superuser:
        # Admins logs
        recent_requests = StockRequest.objects.filter(item__item_type=item_type).order_by('-date_requested')
    else:
        # Regular workers logs
        recent_requests = StockRequest.objects.filter(
            item__item_type=item_type, 
            requester=request.user
        ).order_by('-date_requested')    

    #GET KITS
    kits = BuildKit.objects.filter(components__item__item_type=item_type).distinct()
    
    categories = items.values_list('category', flat=True).distinct()
    
    # URL PARAMETERS 
    category_filter = request.GET.get('category')
    reorder_filter = request.GET.get('reorder')
    priority_filter = request.GET.get('priority')
    station_filter = request.GET.get('station')
    sort_filter = request.GET.get('sort')
    
    # SEARCH LOGIC 
    search_query = request.GET.get('search', '').strip() 
    
    #SEARCH LOGIC 
    if search_query:
        # Filter items where the name contains the search text (case-insensitive)
        items = items.filter(name__icontains=search_query)

    #CATEGORY FILTER
    if category_filter and category_filter != 'All':
        items = items.filter(category=category_filter)
    
    #STATION FILTER 
    if station_filter and station_filter != 'All':
        items = items.filter(station=station_filter)
    
    print("THE BROWSER SENT THIS STATION:", repr(station_filter))
    #SORT LOGIC
    

    #Logic for defect KPI
    if priority_filter and priority_filter != 'All':
        if not isinstance(items, list):
            # Show only items that have actually had a 'Defect Replacement' request
            items = items.filter(stockrequest__priority=priority_filter).distinct()
    

    #LOGIC FOR REORDER KPI\FILTER
    if reorder_filter == 'Yes':
        items = [item for item in items if item.reorder_needed == 'Yes']
    elif reorder_filter == 'No':
        items = [item for item in items if item.reorder_needed == 'No']
    if not isinstance(items, list):
        items = list(items)
    if sort_filter == 'value_desc':
        items.sort(key=lambda x: x.total_value if hasattr(x, 'total_value') else 0, reverse=True)
    
    # RECENT OPERATIONS LOG (Filtered by user/priority)
    if request.user.is_superuser:
        recent_requests = StockRequest.objects.filter(item__item_type=item_type).order_by('-date_requested')
    else:
        recent_requests = StockRequest.objects.filter(item__item_type=item_type, requester=request.user).order_by('-date_requested')    

    if priority_filter and priority_filter != 'All':
        recent_requests = recent_requests.filter(priority=priority_filter)
    
    recent_requests = recent_requests[:10]
    #KPI CALCULATIONS
    total_items_count = len(items) if isinstance(items, list) else items.count()
    low_stock_count = sum(1 for item in items if item.reorder_needed == 'Yes')
    total_inventory_value = sum(item.total_value for item in items)
    defect_stats = StockRequest.objects.filter(
        item__item_type=item_type, 
        priority='Defect Replacement'
    ).aggregate(total=Sum('quantity_requested'))
    defect_count = defect_stats['total'] or 0

    chart_labels = json.dumps([item.name for item in items])
    chart_data = json.dumps([float(item.quantity) for item in items]) 

    if request.method == 'POST':
        # KIT REQUESTS 
        if 'request_kit' in request.POST:
            kit_id = request.POST.get('kit_id')
            qty_to_build = int(request.POST.get('kit_quantity', 1))
            kit = get_object_or_404(BuildKit, id=kit_id)

            # Validation (Do we have enough parts for all components?)
            can_build = True
            missing_parts = []
            
            for component in kit.components.all():
                total_needed = component.quantity_required * qty_to_build
                if component.item.quantity < total_needed:
                    can_build = False
                    missing_parts.append(f"{component.item.name} (Need {total_needed}, Have {component.item.quantity})")


            if can_build:
                for component in kit.components.all():
                    total_needed = component.quantity_required * qty_to_build
                    
                    # Deduct the inventory
                    component.item.quantity -= total_needed
                    component.item.save()
                    
                    # audit log for each part
                    StockRequest.objects.create(
                        item=component.item,
                        quantity_requested=total_needed,
                        requester=request.user
                    )
                messages.success(request, f"Successfully pulled parts for {qty_to_build}x {kit.name}!")
            else:
                # If even ONE part is missing, halt the whole process
                messages.error(request, f"Cannot build {kit.name}. Missing parts: {', '.join(missing_parts)}")
            
            return redirect('dashboard', item_type=item_type)

        # SINGLE ITEM REQUESTS
        else:
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
        'kits': kits, 
        'form': form,
        'recent_requests': recent_requests,
        'categories': categories,
        'total_items_count': total_items_count,
        'low_stock_count': low_stock_count,
        'total_inventory_value': total_inventory_value,
        'defect_count': defect_count,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'search_query': search_query,
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

#EXECUTIVE SUMMARY REPORT
@login_required(login_url='login')
def executive_report(request):
    # SECURITY
    if not request.user.is_superuser:
        messages.error(request, "Access Denied: Executive reporting only.")
        return redirect('landing')

    # Monthly Consumption Math
    current_year = now().year
    current_month = now().month

    #EXECUTIVE SUMMARY (Overall Health)
    all_items = InventoryItem.objects.all()
    
    total_units = sum(item.quantity for item in all_items)
    total_value = sum(item.total_value for item in all_items if hasattr(item, 'total_value')) 

    # INVENTORY PERFORMANCE (At-Risk & Out of Stock)
    out_of_stock = InventoryItem.objects.filter(quantity__lte=0)
    low_stock = InventoryItem.objects.filter(quantity__lte=10)
    
    #STOCK MOVEMENT (Fast-Moving Items by Volume)
    monthly_requests = StockRequest.objects.filter(
        date_requested__year=current_year,
        date_requested__month=current_month
    )
    fast_moving_items = monthly_requests.values('item__name').annotate(
        total_pulled=Sum('quantity_requested')
    ).order_by('-total_pulled')[:20]

    #PRODUCTION SHORTFALLS (Defect Tracking)
    defect_replacements = monthly_requests.filter(
        priority='Defect Replacement'
    ).values('item__name').annotate(
        total_replaced=Sum('quantity_requested')
    ).order_by('-total_replaced')

    #PRIORITY LEVEL ANALYSIS
    priority_breakdown = monthly_requests.values('priority').annotate(
        request_count=Count('id'),
        total_volume=Sum('quantity_requested')
    )

    context = {
        'total_value': total_value,
        'total_units': total_units,
        'out_of_stock': out_of_stock,
        'low_stock': low_stock,
        'fast_moving_items': fast_moving_items,
        'defect_replacements': defect_replacements,
        'priority_breakdown': priority_breakdown,
        'current_month_name': now().strftime("%B %Y"),
        'total_requests': monthly_requests.count(),
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