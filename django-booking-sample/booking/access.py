from .models import Staff


def user_belongs_to_store(user, store):
    """その店舗のスタッフ(またはスーパーユーザー)か。

    店舗内画面(ダッシュボード・座席ボード・SNS承認・在庫)共通の権限判定。
    定義はここ1箇所のみ。変更時は全アプリに波及することに注意。
    """
    return user.is_superuser or Staff.objects.filter(user=user, store=store).exists()
