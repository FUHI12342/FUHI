"""店舗スコープのアクセス制御(全アプリ共通)。

判定ルールはこのモジュールにのみ置く。各ビューは
`check_store_access()` か `StoreAccessMixin` を使い、独自に判定を書かない。

- メンバー判定: スーパーユーザー、またはその店舗の Staff
- 店長判定: 上記のうち is_manager=True(承認・開閉店・CSV など影響の大きい操作)
- 機能フラグ: Store.enable_* が False の機能は 404(存在しない扱い)
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Staff, Store

FEATURE_LABELS = {
    'enable_sns': 'SNS投稿機能',
    'enable_inventory': '在庫・発注機能',
    'enable_seat_board': '座席ボード',
    'enable_gbp': 'Googleマップ(GBP)連携',
    'enable_web_reservation': 'Web座席予約',
}


def user_belongs_to_store(user, store, require_manager=False):
    """その店舗のスタッフ(またはスーパーユーザー)か。"""
    if user.is_superuser:
        return True
    staff = Staff.objects.filter(user=user, store=store)
    if require_manager:
        staff = staff.filter(is_manager=True)
    return staff.exists()


def feature_enabled(store, feature):
    return feature is None or getattr(store, feature)


def require_feature(store, feature):
    """機能フラグがオフなら Http404(存在しない扱い)。公開ページからも使う。"""
    if not feature_enabled(store, feature):
        raise Http404(f'この店舗では{FEATURE_LABELS.get(feature, feature)}が無効です。')


def require_web_reservation(store):
    """顧客向けWeb座席予約が使える店舗か。飲食業態以外・フラグオフは 404。

    ログイン不要の公開機能なので権限判定は無い。判定条件は Store.accepts_web_reservation。
    """
    if not store.accepts_web_reservation:
        raise Http404('この店舗ではWeb座席予約を受け付けていません。')


def check_store_access(user, store, *, feature=None, manager=False):
    """機能フラグ→権限の順に検査し、通らなければ例外を投げる。

    feature: 'enable_sns' 等の Store フラグ名。オフなら Http404。
    manager: True なら店長権限を要求。満たさなければ PermissionDenied。
    """
    require_feature(store, feature)
    if not user.is_authenticated or not user_belongs_to_store(user, store, require_manager=manager):
        raise PermissionDenied


class StoreAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """店舗スコープのクラスベースビュー用。

    サブクラスは `get_store()` を実装する(既定は URL の store_pk / pk から Store を引く)。
    `feature_flag` と `require_manager` で機能フラグ・店長要求を宣言する。
    """
    raise_exception = True
    feature_flag = None
    require_manager = False

    def get_store(self):
        pk = self.kwargs.get('store_pk', self.kwargs.get('pk'))
        return get_object_or_404(Store, pk=pk)

    def test_func(self):
        self.store = self.get_store()
        check_store_access(
            self.request.user, self.store,
            feature=self.feature_flag, manager=self.require_manager,
        )
        return True
