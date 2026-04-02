from django.contrib import admin
from .models import chefsUser, Chef, FoodImages, Dish, Order

admin.site.register(chefsUser)
admin.site.register(Chef)
admin.site.register(FoodImages)
admin.site.register(Dish)
admin.site.register(Order)
