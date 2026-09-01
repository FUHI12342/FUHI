from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.views import generic
from django.views.decorators.http import require_POST

from booking.access import StoreAccessMixin, check_store_access
from booking.models import Store
from .models import Product, PurchaseOrder, StockMovement
from . import services

FEATURE = 'enable_inventory'


class StockList(StoreAccessMixin, generic.TemplateView):
    """在庫一覧と入荷登録・発注案生成の入口。"""
    template_name = 'inventory/stock_list.html'
    feature_flag = FEATURE

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            store=self.store,
            # 商品ごとに Sum を発行しない(1クエリで現在庫を注釈する)
            products=(
                self.store.products.filter(is_active=True)
                .select_related('supplier')
                .annotate(stock=Coalesce(Sum('movements__quantity'), 0))
            ),
            orders=PurchaseOrder.objects.filter(store=self.store).select_related('supplier')[:20],
        )
        return context


class OrderDetail(StoreAccessMixin, generic.DetailView):
    model = PurchaseOrder
    template_name = 'inventory/order_detail.html'
    feature_flag = FEATURE

    def get_store(self):
        return get_object_or_404(PurchaseOrder.objects.select_related('store'), pk=self.kwargs['pk']).store

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order_text'] = self.object.as_text()
        return context


@require_POST
@login_required
def record_arrival(request, product_pk):
    product = get_object_or_404(Product.objects.select_related('store'), pk=product_pk)
    check_store_access(request.user, product.store, feature=FEATURE)
    try:
        quantity = int(request.POST.get('quantity', '0'))
    except ValueError:
        quantity = 0
    if quantity <= 0:
        messages.error(request, '入荷数量は1以上を指定してください。')
    else:
        StockMovement.objects.create(
            product=product, kind=StockMovement.KIND_ARRIVAL, quantity=quantity, created_by=request.user,
        )
        messages.success(request, f'{product.name} を{quantity}{product.unit}入荷登録しました。')
    return redirect('inventory:stock_list', store_pk=product.store.pk)


@require_POST
@login_required
def generate_proposals(request, store_pk):
    store = get_object_or_404(Store, pk=store_pk)
    check_store_access(request.user, store, feature=FEATURE)
    orders = services.generate_order_proposals(store)
    if orders:
        messages.success(request, f'{len(orders)}件の発注案を生成しました。内容を確認して承認してください。')
    else:
        messages.info(request, '発注が必要な商品はありません。')
    return redirect('inventory:stock_list', store_pk=store.pk)


def _get_order_for_manager(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.select_related('supplier', 'store'), pk=pk)
    check_store_access(request.user, order.store, feature=FEATURE, manager=True)
    return order


@require_POST
@login_required
def approve_order(request, pk):
    order = _get_order_for_manager(request, pk)
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
def receive_order(request, pk):
    order = _get_order_for_manager(request, pk)
    if order.status != PurchaseOrder.STATUS_SENT:
        messages.error(request, '入荷待ちの発注ではありません。')
    else:
        services.mark_received(order)
        messages.success(request, '入荷済みにし、発注数量を在庫へ反映しました。')
    return redirect('inventory:order_detail', pk=order.pk)


@require_POST
@login_required
def cancel_order(request, pk):
    order = _get_order_for_manager(request, pk)
    if order.status == PurchaseOrder.STATUS_PROPOSED:
        order.status = PurchaseOrder.STATUS_CANCELLED
        order.save(update_fields=['status'])
        messages.success(request, '発注案を取り消しました。')
    return redirect('inventory:stock_list', store_pk=order.store.pk)
