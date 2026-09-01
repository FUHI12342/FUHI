import django.dispatch

# 開店操作をトリガーに連鎖する自動処理のためのシグナル。
# レシーバは sns / inventory 等の各アプリが接続する。
# レシーバ内で失敗した場合は、例外を握りつぶさず ChecklistTask(alert付き)を作って
# 人間が開店チェックリスト上で検知できるようにすること。
store_opened = django.dispatch.Signal()  # kwargs: business_day, user
