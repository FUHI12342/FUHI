from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from booking.models import Store
from operations.views import user_belongs_to_store
from .models import Product, PurchaseOrder, StockMovement
from . import services


class StockList(LoginRequiredMixin, UserPassesTestMixin, generic.TemplateView):
    """在庫一覧と入荷登録・発注案生成の入口。"""
    template_name = 'inventory/stock_list.html'
    raise_exception = True

    def test_func(self):
        store = get_object_or_404(Store, pk=self.kwargs['store_pk'])
        return user_belongs_to_store(self.request.user, store)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = get_object_or_404(Store, pk=self.kwargs['store_pk'])
        context['store'] = store
        context['products'] = store.products.filter(is_active=True)
        context['orders'] = PurchaseOrder.objects.filter(store=store).select_related('supplier')[:20]
        return context


@require_POST
@login_required
def record_arrival(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    if not user_belongs_to_store(request.user, product.store):
        raise PermissionDenied
    try:
        quantity = int(request.POST.get('quantity', '0'))
    except ValueError:
        quantity = 0
    if quantity <= 0:
        messages.error(request, '入荷数量は1以上を指定してください。')
    else:
        StockMovement.objects.create(
            product=product, kind=StockMovement.KIND_ARRIVAL,
            quantity=quantity, created_by=request.user,
        )
        messages.success(request, f'{product.name} を{quantity}{product.unit}入荷登録しました。')
    return redirect('inventory:stock_list', store_pk=product.store.pk)


@require_POST
@login_required
def generate_proposals(request, store_pk):
    store = get_object_or_404(Store, pk=store_pk)
    if not user_belongs_to_store(request.user, store):
        raise PermissionDenied
    orders = services.generate_order_proposals(store)
    if orders:
        messages.success(request, f'{len(orders)}件の発注案を生成しました。内容を確認して承認してください。')
    else:
        messages.info(request, '発注が必要な商品はありません。')
    return redirect('inventory:stock_list', store_pk=store.pk)


class OrderDetail(LoginRequiredMixin, UserPassesTestMixin, generic.DetailView):
    model = PurchaseOrder
    template_name = 'inventory/order_detail.html'
    raise_exception = True

    def test_func(self):
        order = get_object_or_404(PurchaseOrder, pk=self.kwargs['pk'])
        return user_belongs_to_store(self.request.user, order.store)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order_text'] = self.object.as_text()
        return context


@require_POST
@login_required
def approve_order(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.select_related('supplier', 'store'), pk=pk)
    if not user_belongs_to_store(request.user, order.store):
        raise PermissionDenied
    if order.status != PurchaseOrder.STATUS_PROPOSED:
        messages.error(request, 'この発注はすでに処理済みです。')
    else:
        services.approve_and_send(order, request.user)
        if order.note:
            messages.warning(request, order.note)
        else:
            messages.success(request, f'{order.supplier.name} へ発注メールを送信しました。')
    return redirect('inventory:order_detail', pk=order.pk)


@require_POST
@login_required
def cancel_order(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.select_related('store'), pk=pk)
    if not user_belongs_to_store(request.user, order.store):
        raise PermissionDenied
    if order.status == PurchaseOrder.STATUS_PROPOSED:
        order.status = PurchaseOrder.STATUS_CANCELLED
        order.save(update_fields=['status'])
        messages.success(request, '発注案を取り消しました。')
    return redirect('inventory:stock_list', store_pk=order.store.pk)
