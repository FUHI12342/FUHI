from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('store/<int:store_pk>/', views.StockList.as_view(), name='stock_list'),
    path('product/<int:product_pk>/arrival/', views.record_arrival, name='record_arrival'),
    path('store/<int:store_pk>/proposals/', views.generate_proposals, name='generate_proposals'),
    path('order/<int:pk>/', views.OrderDetail.as_view(), name='order_detail'),
    path('order/<int:pk>/approve/', views.approve_order, name='approve_order'),
    path('order/<int:pk>/cancel/', views.cancel_order, name='cancel_order'),
]
