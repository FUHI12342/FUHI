from .models import Staff


def user_belongs_to_store(user, store, require_manager=False):
    """その店舗のスタッフ(またはスーパーユーザー)か。

    店舗内画面(ダッシュボード・座席ボード・SNS承認・在庫)共通の権限判定。
    require_manager=True の場合は店長フラグ(承認権限)を持つスタッフに限定する。
    対外影響・金銭影響のある操作(SNS承認・発注承認/取消/入荷・開閉店・勤怠CSV)は
    必ず require_manager=True で呼ぶこと。定義はここ1箇所のみ。
    """
    if user.is_superuser:
        return True
    staff = Staff.objects.filter(user=user, store=store)
    if require_manager:
        staff = staff.filter(is_manager=True)
    return staff.exists()
