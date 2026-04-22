from django import forms
from .models import StockRequest, InventoryItem

class StockRequestForm(forms.ModelForm):
    class Meta:
        model = StockRequest
        fields = ['item', 'quantity_requested', 'priority']

        widgets = {
            'item': forms.Select(attrs={'class': 'form-select'}),
            'quantity_requested': forms.NumberInput(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }

        labels = {
            'item': 'Item Name',
            'quantity_requested': 'Quantity Needed',
            'priority': 'Priority / Reason',
        }
    def __init__(self, *args, **kwargs):
        item_type = kwargs.pop('item_type', None)
        super(StockRequestForm, self).__init__(*args, **kwargs)
        if item_type:
            self.fields['item'].queryset = InventoryItem.objects.filter(item_type=item_type)