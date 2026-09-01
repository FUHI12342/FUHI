from django.urls import path
from . import views

app_name = 'sns'

urlpatterns = [
    path('store/<int:store_pk>/drafts/', views.DraftList.as_view(), name='draft_list'),
    path('store/<int:store_pk>/regenerate/', views.regenerate, name='regenerate'),
    path('draft/<int:pk>/', views.DraftDetail.as_view(), name='draft_detail'),
    path('draft/<int:pk>/approve/', views.approve, name='approve'),
]
