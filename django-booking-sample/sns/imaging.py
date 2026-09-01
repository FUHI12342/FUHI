"""SNS投稿画像の自動生成(Pillow)。

店舗テンプレ(背景色+ロゴ的な店名)に日付と出勤キャスト名を載せた
1080x1080 の告知画像を合成する。キャストのプロフィール画像は
sns_publishable=True のスタッフ分のみ貼り込む(顔出しNG対応)。
"""
import glob
import io
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = (1080, 1080)
BG_COLOR = (24, 24, 48)
ACCENT = (240, 200, 80)
TEXT_COLOR = (255, 255, 255)


def _font_candidates():
    yield os.environ.get('SNS_IMAGE_FONT', '')
    yield '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    yield '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'
    yield '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
    yield '/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc'
    # Debian の fonts-noto-cjk はバージョンによりファイル名が異なる(VF版など)ため走査する
    for pattern in ('/usr/share/fonts/**/*CJK*.ttc', '/usr/share/fonts/**/*CJK*.otf'):
        yield from glob.glob(pattern, recursive=True)


def _load_font(size):
    """日本語グリフを持つフォントを探す。無ければ Pillow デフォルト。"""
    for path in _font_candidates():
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def generate_open_image(store_name, date, cast_shifts):
    """開店告知画像を生成し PNG バイト列を返す。

    cast_shifts: attendance.Shift の列(publishable_casts で絞り込み済みのもの)。
    """
    image = Image.new('RGB', SIZE, BG_COLOR)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(80)
    sub_font = _load_font(48)
    cast_font = _load_font(40)

    draw.rectangle([(0, 0), (SIZE[0], 12)], fill=ACCENT)
    draw.text((60, 80), store_name, font=title_font, fill=TEXT_COLOR)
    draw.text((60, 200), f'{date:%Y/%m/%d} OPEN!', font=sub_font, fill=ACCENT)

    y = 320
    if cast_shifts:
        draw.text((60, y), '本日の出勤', font=sub_font, fill=TEXT_COLOR)
        y += 90
        x = 60
        for shift in cast_shifts:
            staff = shift.staff
            avatar_size = 160
            if staff.profile_image:
                try:
                    avatar = Image.open(staff.profile_image.path).convert('RGB')
                    avatar.thumbnail((avatar_size, avatar_size))
                    image.paste(avatar, (x, y))
                except (OSError, ValueError):
                    draw.rectangle([(x, y), (x + avatar_size, y + avatar_size)], outline=ACCENT, width=3)
            else:
                draw.rectangle([(x, y), (x + avatar_size, y + avatar_size)], outline=ACCENT, width=3)
            label = f'{staff.name} {shift.start_time:%H:%M}〜'
            draw.text((x, y + avatar_size + 10), label, font=cast_font, fill=TEXT_COLOR)
            x += avatar_size + 60
            if x > SIZE[0] - avatar_size - 60:
                x = 60
                y += avatar_size + 90
        y += 260

    draw.rectangle([(0, SIZE[1] - 12), SIZE], fill=ACCENT)

    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()
