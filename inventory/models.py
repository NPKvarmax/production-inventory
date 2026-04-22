from django.db import models
from django.contrib.auth.models import User

#Inventory Item Model
class InventoryItem(models.Model):
    TYPE_CHOICES = [
        ('Part', 'Part'),
        ('Fastener', 'Fastener'),
    ]
    name = models.CharField(max_length=200)
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Part')
    category = models.CharField(max_length=100, default="Uncategorized")
    stock_in = models.PositiveIntegerField(default=0)
    quantity = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    @property
    def total_value(self):
        return self.quantity * self.unit_cost
    @property
    def reorder_needed(self):
        if self.stock_in > 0 and self.quantity <= (self.stock_in / 4):
            return "Yes"
        return "No"
    
    def __str__(self):
        return f"[{self.item_type}] {self.name}"


#Stock Request Model
class StockRequest(models.Model):
    PRIORITY_CHOICES = [
        ('Standard Production Batch', 'Standard Production Batch'),
        ('Defect Replacement', 'Defect Replacement'),
        ('R&D Prototype', 'R&D Prototype'),
        ('Maintenance Consumable', 'Maintenance Consumable'),
    ]
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity_requested = models.PositiveIntegerField()
    priority = models.CharField(max_length=50, choices=PRIORITY_CHOICES, default='Standard Production Batch')
    requester = models.ForeignKey(User, on_delete=models.CASCADE)
    date_requested = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.quantity_requested}x {self.item.name} ({self.priority}) by {self.requester.username}"    
    
    