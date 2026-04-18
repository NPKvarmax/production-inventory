from django.db import models
from django.contrib.auth.models import User

#Inventory Item Model
class InventoryItem(models.Model):
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=0)
    def __str__(self):
        return self.name


#Stock Request Model
class StockRequest(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity_requested = models.PositiveIntegerField()
    requester = models.ForeignKey(User, on_delete=models.CASCADE)
    date_requested = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.quantity_requested} x {self.item.name} requested by {self.requester.username}"
    
    
    