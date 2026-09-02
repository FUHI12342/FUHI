"""顧客向けWeb座席予約のフォーム。"""
import datetime

from django import forms
from django.utils import timezone

from .models import Schedule
from .reservations import MAX_DAYS_AHEAD


class ReservationSearchForm(forms.Form):
    """人数と日付から空き座席候補を探す。"""
    date = forms.DateField(label='日付', widget=forms.DateInput(attrs={'type': 'date'}))
    party_size = forms.IntegerField(label='人数', min_value=1, max_value=99, initial=2)

    def clean_date(self):
        date = self.cleaned_data['date']
        today = timezone.localdate()
        if date < today:
            raise forms.ValidationError('過ぎた日付は選べません。')
        if date > today + datetime.timedelta(days=MAX_DAYS_AHEAD):
            raise forms.ValidationError(f'予約は{MAX_DAYS_AHEAD}日先まで受け付けています。')
        return date


class ReservationForm(forms.ModelForm):
    """予約確定時の連絡先入力。メールは確認・キャンセル導線(ノーショー対策)に必須。"""
    class Meta:
        model = Schedule
        fields = ('name', 'customer_email', 'customer_phone')
        labels = {'name': 'お名前', 'customer_email': 'メールアドレス', 'customer_phone': '電話番号(任意)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer_email'].required = True
