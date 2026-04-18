from django import forms
from .models import StockRequest

class StockRequestForm(forms.ModelForm):
    class Meta:
        model = StockRequest
        fields = ['item', 'quantity_requested']