import json
import csv
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.http import HttpResponse

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
    recent_requests = StockRequest.objects.filter(item__item_type=item_type).order_by('-date_requested')[:10]
    
    categories = items.values_list('category', flat=True).distinct()
    
    category_filter = request.GET.get('category')
    reorder_filter = request.GET.get('reorder')
    priority_filter = request.GET.get('priority')
    
    if category_filter and category_filter != 'All':
        items = items.filter(category=category_filter)
        
    if reorder_filter == 'Yes':
        items = [item for item in items if item.reorder_needed == 'Yes']
    elif reorder_filter == 'No':
        items = [item for item in items if item.reorder_needed == 'No']
        
    if priority_filter and priority_filter != 'All':
        recent_requests = recent_requests.filter(priority=priority_filter)

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
                return redirect('dashboard', item_type=item_type) # Redirect back to the same department
            else:
                messages.error(request, f"Error: You requested {requested_qty}, but only {requested_item.quantity} are available.")
    else:
        form = StockRequestForm(item_type=item_type) # Pass it for GET requests too

    context = {
        'item_type': item_type, # Send the type to the HTML to update titles
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
        return redirect('landing') # Redirect to landing instead of dashboard

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('landing') # Redirect to landing instead of dashboard
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