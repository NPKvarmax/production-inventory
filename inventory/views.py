from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import InventoryItem
from .forms import StockRequestForm
from .models import InventoryItem, StockRequest
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout

@login_required(login_url='/admin/login/') 
def dashboard(request):
    items = InventoryItem.objects.all()
    recent_requests = StockRequest.objects.all().order_by('-date_requested')[:10]
    # 1. Did the user just click 'Submit' on the form? (A POST request)
    if request.method == 'POST':
        form = StockRequestForm(request.POST)
        if form.is_valid():
            # Don't save to the database just yet...
            stock_request = form.save(commit=False)
            
            # Grab the specific item they want to withdraw
            requested_item = stock_request.item
            requested_qty = stock_request.quantity_requested
            
            # --- THE CRITICAL LOGIC ---
            # 2. Check if we have enough in stock
            if requested_qty <= requested_item.quantity:
                # Deduct the stock
                requested_item.quantity -= requested_qty
                requested_item.save() # Update the inventory database
                
                # Assign the logged-in user as the requester, then save the request
                stock_request.requester = request.user
                stock_request.save()
                
                # Send a success message to the screen
                messages.success(request, f"Successfully requested {requested_qty} of {requested_item.name}.")
                return redirect('dashboard') # Refresh the page safely
            else:
                # 3. Not enough stock! Send an error message.
                messages.error(request, f"Error: You requested {requested_qty}, but only {requested_item.quantity} are available.")
    
    # If they just visited the page normally (a GET request), give them an empty form
    else:
        form = StockRequestForm()

    context = {
        'items': items,
        'form': form
    }
    return render(request, 'inventory/dashboard.html', context)

def login_page(request):
    # If the user is already logged in, don't show the login page again
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # Django's built-in form that checks usernames and passwords
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user) # This actually logs the user in securely
            return redirect('dashboard')
    else:
        form = AuthenticationForm()

    context = {'form': form}
    return render(request, 'inventory/login.html', context)


def logout_user(request):
    logout(request) 
    return redirect('login') 