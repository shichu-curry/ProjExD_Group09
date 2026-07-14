# -*- coding: utf-8 -*-
"""
Swarm Night
これは見下ろし型サバイバル（Vampire Survivors風）のベース機能(土台)です

ベース機能:
  1. メインループとゲーム状態管理 (PLAY / GAMEOVER)
  2. プレイヤー: 8方向移動・HP・被弾無敵時間
  3. 敵: 1種類、画面外から湧いてプレイヤーへ直進
  4. 武器: 1種類、最も近い敵へ自動発射
  5. 当たり判定: 弾×敵 / 敵×プレイヤー
  6. HUD: HPバー・経過時間・撃破数
  7. ゲームオーバー: 表示とリスタート

今後追加機能を個人で実装するにあたって、取り組みやすくなるように、拡張ポイントには [拡張] コメントを付けている。
"""


import os
import math
import random
import sys

import pygame


# （画像・音声素材を相対パスで読み込めるようにするため）
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# =========================================================
# 定数（バランス調整はここに集約）
# [拡張] 難易度上昇機能は、この値を時間経過で変化させる形で実装してもいいのでは
# =========================================================

WIDTH, HEIGHT = 1100, 650
FPS = 60

PLAYER_SPEED   = 4.5     # プレイヤー移動速度 (px/frame)
PLAYER_MAX_HP  = 100
INVINCIBLE_MS  = 1000    # 被弾後の無敵時間 (ミリ秒)

ENEMY_SPEED    = 1.8
ENEMY_HP       = 3
ENEMY_DAMAGE   = 10      # 接触ダメージ
SPAWN_INTERVAL = 900     # 敵の湧き間隔 (ミリ秒)

BULLET_SPEED   = 9.0
BULLET_DAMAGE  = 1
FIRE_INTERVAL  = 400     # 自動発射の間隔 (ミリ秒)

COL_BG     = (24, 28, 24)
COL_TEXT   = (240, 240, 240)
COL_HP_BG  = (70, 30, 30)
COL_HP_FG  = (60, 200, 90)


# =========================================================
# ユーティリティ
# =========================================================
# 日本語フォントが見つかったかどうか（見つからなければ英語表記に切替）

JP_FONT_PATH = None


def _find_jp_font_path():
    """日本語フォントのファイルパスを探す。
    match_font は macOS のヒラギノ等を見つけられないことがあるため、
    1) OS別の実ファイルパス → 2) match_font → 3) get_fonts() 走査 の順で探索。"""
    #OSごとの代表的なフォントファイルを直接確認
    candidates = [
        # macOS
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Windows
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf",
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            return path
    #フォント名からの探索
    for name in ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic",
                 "Meiryo", "Noto Sans CJK JP", "MS Gothic", "TakaoPGothic",
                 "IPAGothic"]:
        path = pygame.font.match_font(name)
        if path:
            return path
    #システムフォント一覧から日本語系らしき名前を走査
    keywords = ("hiragino", "gothic", "meiryo", "yugoth", "noto", "ipa",
                "takao", "mincho", "osaka")
    for name in pygame.font.get_fonts():
        if any(k in name for k in keywords):
            path = pygame.font.match_font(name)
            if path:
                return path
    return None


def load_font(size):
    """日本語対応フォントを返す。見つからなければデフォルト
    （その場合、日本語文字列は英語表記に切り替えられる）。"""
    global JP_FONT_PATH
    if JP_FONT_PATH is None:
        JP_FONT_PATH = _find_jp_font_path() or ""
    if JP_FONT_PATH:
        return pygame.font.Font(JP_FONT_PATH, size)
    return pygame.font.SysFont(None, size)


def jp_available():
    """日本語フォントが使えるか。"""
    return bool(JP_FONT_PATH)


def make_diamond_surf(size, color, border=None):
    """♦（ひし形）のSurfaceを作る。経験値ジェムの描画に使用。"""
    w = h = size * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    points = [(size, 0), (w, size), (size, h), (0, size)]
    pygame.draw.polygon(surf, color, points)
    if border:
        pygame.draw.polygon(surf, border, points, 2)
    return surf


def make_heart_surf(size, color, border=None):
    """ハート形のSurfaceを作る。回復アイテムの描画に使用。"""
    w = h = size * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w / 2
    lobe_r = size * 0.55
    points = []
    for i in range(9):
        heart = math.pi * (1.0 - i / 8)
        points.append((cx - lobe_r + lobe_r * math.cos(heart),
                       lobe_r + lobe_r * math.sin(heart) - lobe_r * 0.15))
    for i in range(9):
        heart = math.pi * (1.0 - i / 8)
        points.append((cx + lobe_r - lobe_r * math.cos(heart),
                       lobe_r + lobe_r * math.sin(heart) - lobe_r * 0.15))
    points.append((cx, h))
    pygame.draw.polygon(surf, color, points)
    if border:
        pygame.draw.polygon(surf, border, points, 2)
    return surf

def make_circle_surf(radius, color, border=None):
    """円形のSurfaceを作る（画像素材が無くても動くように）。
    [拡張] こうかとん画像を使う場合はここを pygame.image.load に差し替える"""
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, color, (radius, radius), radius)
    if border:
        pygame.draw.circle(surf, border, (radius, radius), radius, 2)
    return surf


def load_image(path, size, fallback_color): #追加機能実装(杉本)
    """fig/ 内の武器画像(png)を読み込む。
        白背景が焼き込まれた画像でも透過されるように、左上ピクセルの色を背景色とみなして透過処理を追加
        縦横比を保ったまま size の枠内に収めるよう変更"""
    if os.path.exists(path):
        img = pygame.image.load(path).convert_alpha()
        corner = img.get_at((0, 0))
        if corner.a == 255:  # 透過情報が無い場合の処理
            keyed = pygame.image.load(path).convert()
            keyed.set_colorkey((corner.r, corner.g, corner.b))  # 左上の色を背景色とみなして透過させる
            img = pygame.Surface(keyed.get_size(), pygame.SRCALPHA)
            img.blit(keyed, (0, 0))
        w, h = img.get_size()
        scale = min(size[0] / w, size[1] / h)
        return pygame.transform.smoothscale(
            img, (max(1, round(w * scale)), max(1, round(h * scale))))
    surf = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(surf, fallback_color, surf.get_rect(), border_radius=4)
    return surf


# =========================================================
# 2. プレイヤー
# =========================================================

class Player(pygame.sprite.Sprite):
    """こうかとん（プレイヤー）
    [拡張] レベル・経験値・ステータス強化は、このクラスに
           exp / level 属性と level_up() メソッドを足す形で実装できる。
           speed や max_hp を書き換えるだけでアップグレードが効く設計。"""

    def __init__(self, pos):
        super().__init__()
        self.image = make_circle_surf(16, (250, 210, 80), (120, 90, 20))
        self.rect = self.image.get_rect(center=pos)
        self.speed = PLAYER_SPEED
        self.max_hp = PLAYER_MAX_HP
        self.hp = self.max_hp
        self.invincible_until = 0  # この時刻まで無敵
        self.facing = (1.0, 0.0)   # 最後に移動した方向（槍・斧が参照）追加機能実装(杉本)
        self.exp = 0  # 経験値ジェム取得の受け皿

    def update(self, keys, now):
        #8方向移動
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - \
             (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - \
             (keys[pygame.K_w] or keys[pygame.K_UP])
        if dx and dy:  # 斜め移動の速度を正規化
            dx *= 0.7071
            dy *= 0.7071
        if dx or dy:
            self.facing = (dx, dy)  # 移動中だけ向きを更新　追加機能実装(杉本)
        self.rect.x += dx * self.speed
        self.rect.y += dy * self.speed
        self.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
        # [拡張] ダッシュ機能: Shift押下中は speed を一時的に倍にする等

    def take_damage(self, amount, now):
        """被弾処理。無敵時間中はダメージを受けない。"""
        if now < self.invincible_until:
            return
        self.hp -= amount
        self.invincible_until = now + INVINCIBLE_MS
        # [拡張] ノックバック・被弾SEはここに追加

    def heal(self, amount):
        """回復アイテム取得時などに呼ぶ。max_hpを超えない。"""
        self.hp = min(self.max_hp, self.hp + amount)

    def is_invincible(self, now):
        return now < self.invincible_until

    def draw(self, screen, now):
        # 無敵時間中は点滅させる
        if self.is_invincible(now) and (now // 100) % 2 == 0:
            return
        screen.blit(self.image, self.rect)


# =========================================================
# 3. 敵
# =========================================================

class Enemy(pygame.sprite.Sprite):
    """雑魚敵: プレイヤーに向かって直進するだけ。
    [拡張] 敵の種類追加はこのクラスを継承して
           update() や属性 (speed/hp/damage) を上書きする。
           例: class DashEnemy(Enemy), class RangedEnemy(Enemy), class Boss(Enemy)"""

    def __init__(self, pos):
        super().__init__()
        self.image = make_circle_surf(14, (200, 70, 70), (90, 20, 20))
        self.rect = self.image.get_rect(center=pos)
        self.speed = ENEMY_SPEED
        self.hp = ENEMY_HP
        self.damage = ENEMY_DAMAGE

    def update(self, player):
        # プレイヤーへ向かうベクトルを正規化して移動
        vx = player.rect.centerx - self.rect.centerx
        vy = player.rect.centery - self.rect.centery
        dist = math.hypot(vx, vy)
        if dist > 0:
            self.rect.x += vx / dist * self.speed
            self.rect.y += vy / dist * self.speed

    def take_damage(self, amount):
        """被ダメージ。死んだら True を返す。
        [拡張] アイテムドロップ機能は、死亡時ここ（または呼び出し側）で
               経験値ジェムや回復アイテムを生成する"""
        self.hp -= amount
        if self.hp <= 0:
            self.kill()
            return True
        return False


def spawn_enemy(enemies, now_ms):
    """画面外のランダムな位置に敵を1体湧かせる。
    [拡張] 難易度上昇: now_ms（経過時間）に応じて湧き数・敵HP・速度を
           増やす処理をこの関数に足す。
    [拡張] ウェーブ制: 「何秒にどの敵を何体」というテーブルを参照する形に
           書き換えるとウェーブ管理機能になる"""
    side = random.randint(0, 3)
    margin = 30
    if side == 0:    # 上
        pos = (random.randint(0, WIDTH), -margin)
    elif side == 1:  # 下
        pos = (random.randint(0, WIDTH), HEIGHT + margin)
    elif side == 2:  # 左
        pos = (-margin, random.randint(0, HEIGHT))
    else:            # 右
        pos = (WIDTH + margin, random.randint(0, HEIGHT))
    enemies.add(Enemy(pos))


# =========================================================
# 4. 武器・弾
# =========================================================

class Bullet(pygame.sprite.Sprite):
    """直進する弾。画面外に出たら消える。
    [拡張] 貫通弾: 命中時に kill() しない pierce 属性を足す。
    [拡張] 範囲爆発: 命中時に周囲の敵にもダメージを与える処理を追加"""

    def __init__(self, pos, target_pos):
        super().__init__()
        self.image = make_circle_surf(5, (120, 200, 255))
        self.rect = self.image.get_rect(center=pos)
        vx = target_pos[0] - pos[0]
        vy = target_pos[1] - pos[1]
        dist = math.hypot(vx, vy) or 1
        self.vx = vx / dist * BULLET_SPEED
        self.vy = vy / dist * BULLET_SPEED
        self.damage = BULLET_DAMAGE
        # rectは整数座標なので、精度維持のためfloat座標を別に持つ
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (round(self.x), round(self.y))
        if not pygame.Rect(-50, -50, WIDTH + 100, HEIGHT + 100).colliderect(self.rect):
            self.kill()


class Weapon:
    """自動発射武器の基本形: クールダウンが切れたら最も近い敵を撃つ。
    [拡張] 武器の種類追加はチーム分担の主戦場。
           このクラスと同じ「update(now, ...) を毎フレーム呼ばれ、
           クールダウンが切れたら発動する」形に揃えれば、
           回転オービット・範囲爆発・レーザー等を独立クラスで追加できる。
           プレイヤーが複数武器を持てるよう、main側は weapons リストで管理している"""

    def __init__(self):
        self.interval = FIRE_INTERVAL
        self.last_fired = 0

    def update(self, now, player, enemies, bullets, attacks): #attacksも追加　追加実装(杉本)
        if now - self.last_fired < self.interval:
            return
        target = self._nearest_enemy(player, enemies)
        if target is None:
            return
        bullets.add(Bullet(player.rect.center, target.rect.center))
        self.last_fired = now
        # [拡張] 発射SE、マズルフラッシュ等の演出はここ

    @staticmethod
    def _nearest_enemy(player, enemies):
        nearest, best = None, float("inf")
        px, py = player.rect.center
        for e in enemies:
            d = (e.rect.centerx - px) ** 2 + (e.rect.centery - py) ** 2
            if d < best:
                best, nearest = d, e
        return nearest

# =========================================================
# 5. アイテム（経験値ジェム・回復アイテム）
# =========================================================

EXP_GEM_COLOR    = (80, 220, 255)
EXP_GEM_BORDER   = (20, 120, 170)
HEAL_ITEM_COLOR  = (240, 70, 100)
HEAL_ITEM_BORDER = (150, 20, 40)
HEAL_AMOUNT = 20
HEAL_DROP_RATE = 0.15


class ExpGem(pygame.sprite.Sprite):
    def __init__(self, pos, value=1):
        super().__init__()
        self.image = make_diamond_surf(9, EXP_GEM_COLOR, EXP_GEM_BORDER)
        self.rect = self.image.get_rect(center=pos)
        self.value = value


class HealItem(pygame.sprite.Sprite):
    def __init__(self, pos):
        super().__init__()
        self.image = make_heart_surf(11, HEAL_ITEM_COLOR, HEAL_ITEM_BORDER)
        self.rect = self.image.get_rect(center=pos)
        self.heal_amount = HEAL_AMOUNT


def spawn_item_drop(pos, items):
    items.add(ExpGem(pos, value=random.randint(1, 3)))
    if random.random() < HEAL_DROP_RATE:
        items.add(HealItem(pos))


def collect_items(player, items):
    picked = pygame.sprite.spritecollide(player, items, True)
    for item in picked:
        if isinstance(item, ExpGem):
            player.exp += item.value
        elif isinstance(item, HealItem):
            player.heal(item.heal_amount)

# ---------------------------------------------------------
# 追加武器: 剣（回転斬撃）・槍（突き）・斧（投擲）
# いずれも「attacks グループに攻撃スプライトを生成する」武器。
# 攻撃スプライトは hit_ids で「同じ敵に1回だけ当たる」貫通型。
# ---------------------------------------------------------

class SwordSlash(pygame.sprite.Sprite):
    """剣: プレイヤーの周囲を一回転する斬撃。"""
    DURATION = 600   # 一回転にかかる時間 (ms)
    RADIUS = 70      # プレイヤーからの距離
    DAMAGE = 2
 
    def __init__(self, player, now, base_image):
        super().__init__()
        self.player = player          # 回転中心（常にプレイヤーに追従）
        self.t0 = now
        self.base_image = base_image
        self.damage = self.DAMAGE
        self.hit_ids = set()          # 命中済みの敵（多段ヒット防止）
        fx, fy = player.facing
        self.angle0 = math.degrees(math.atan2(fy, fx))  # 向いている方向から回り始める
        self._place(now)
 
    def _place(self, now):
        t = min(1.0, (now - self.t0) / self.DURATION)
        ang = self.angle0 + 360 * t
        rad = math.radians(ang)
        cx = self.player.rect.centerx + self.RADIUS * math.cos(rad)
        cy = self.player.rect.centery + self.RADIUS * math.sin(rad) # 刃先が進行方向を向くように回転（画像は右向きが基準）
        self.image = pygame.transform.rotate(self.base_image, -ang)
        self.rect = self.image.get_rect(center=(cx, cy))
 
    def update(self, now):
        if now - self.t0 >= self.DURATION:
            self.kill()
            return
        self._place(now)
 
 
class SpearThrust(pygame.sprite.Sprite):
    """槍: 向いている方向へ突き出して戻る、直線の貫通攻撃。"""
    DURATION = 300   # 突いて戻るまでの時間 (ms)
    REACH = 110      # 最大リーチ
    DAMAGE = 2
 
    def __init__(self, player, now, base_image):
        super().__init__()
        self.player = player
        self.t0 = now
        self.damage = self.DAMAGE
        self.hit_ids = set()
        fx, fy = player.facing
        d = math.hypot(fx, fy) or 1
        self.dir = (fx / d, fy / d)   # 発動時の向きで固定
        ang = math.degrees(math.atan2(self.dir[1], self.dir[0]))
        self.image = pygame.transform.rotate(base_image, -ang)
        self._place(now)
 
    def _place(self, now):
        t = min(1.0, (now - self.t0) / self.DURATION)
        dist = 30 + (self.REACH - 30) * math.sin(math.pi * t)  # 伸びて戻る
        cx = self.player.rect.centerx + self.dir[0] * dist
        cy = self.player.rect.centery + self.dir[1] * dist
        self.rect = self.image.get_rect(center=(cx, cy))
 
    def update(self, now):
        if now - self.t0 >= self.DURATION:
            self.kill()
            return
        self._place(now)
 
 
class AxeProjectile(pygame.sprite.Sprite):
    """斧: 放物線を描いて飛ぶ投擲武器（重力あり・回転しながら飛ぶ・貫通）。"""
    GRAVITY = 0.35
    DAMAGE = 3
 
    def __init__(self, pos, direction, base_image):
        super().__init__()
        self.base_image = base_image
        self.damage = self.DAMAGE
        self.hit_ids = set()
        self.x, self.y = float(pos[0]), float(pos[1])
        self.vx = direction * random.uniform(2.0, 4.0)   # 左右方向
        self.vy = -random.uniform(9.0, 12.0)             # 上向きに投げる
        self.spin = random.choice([-1, 1]) * 12          # 回転速度 (度/フレーム)
        self.angle = 0.0
        self.image = base_image
        self.rect = self.image.get_rect(center=pos)
 
    def update(self, now):
        self.vy += self.GRAVITY
        self.x += self.vx
        self.y += self.vy
        self.angle = (self.angle + self.spin) % 360
        self.image = pygame.transform.rotate(self.base_image, self.angle)
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))
        if self.y > HEIGHT + 60 or self.x < -60 or self.x > WIDTH + 60:
            self.kill()
 
 
class SwordWeapon:
    """一定間隔で回転斬撃を出す。"""
    def __init__(self, image):
        self.interval = 2000
        self.last_fired = 0
        self.image = image
 
    def update(self, now, player, enemies, bullets, attacks):
        if now - self.last_fired < self.interval:
            return
        attacks.add(SwordSlash(player, now, self.image))
        self.last_fired = now
 
 
class SpearWeapon:
    """一定間隔で向いている方向へ突きを出す。"""
    def __init__(self, image):
        self.interval = 1500
        self.last_fired = 0
        self.image = image
 
    def update(self, now, player, enemies, bullets, attacks):
        if now - self.last_fired < self.interval:
            return
        attacks.add(SpearThrust(player, now, self.image))
        self.last_fired = now
 
 
class AxeWeapon:
    """一定間隔で斧を放物線投擲する。最も近い敵のいる側へ投げる。"""
    def __init__(self, image):
        self.interval = 2500
        self.last_fired = 0
        self.image = image
 
    def update(self, now, player, enemies, bullets, attacks):
        if now - self.last_fired < self.interval:
            return
        target = Weapon._nearest_enemy(player, enemies)
        if target is not None:
            direction = 1 if target.rect.centerx >= player.rect.centerx else -1
        else:
            direction = 1 if player.facing[0] >= 0 else -1
        attacks.add(AxeProjectile(player.rect.center, direction, self.image))
        self.last_fired = now
 

# =========================================================
# 6. UI
# =========================================================

def draw_hud(screen, font, player, elapsed_ms, kills):
    """HPバー・経過時間・撃破数のみの最小HUD。
    [拡張] 経験値バー・レベル表示・ウェーブ表示などはここに追記"""
    # HPバー
    bar_w, bar_h = 240, 18
    pygame.draw.rect(screen, COL_HP_BG, (20, 20, bar_w, bar_h), border_radius=4)
    ratio = max(0, player.hp / player.max_hp)
    pygame.draw.rect(screen, COL_HP_FG,
                     (20, 20, int(bar_w * ratio), bar_h), border_radius=4)
    hp_text = font.render(f"HP {max(0, player.hp)}/{player.max_hp}",
                          True, COL_TEXT)
    screen.blit(hp_text, (270, 18))

    # 経過時間 (MM:SS)
    sec = elapsed_ms // 1000
    time_text = font.render(f"TIME {sec // 60:02d}:{sec % 60:02d}",
                            True, COL_TEXT)
    screen.blit(time_text, time_text.get_rect(midtop=(WIDTH // 2, 18)))

    # 撃破数
    kill_text = font.render(f"KILL {kills}", True, COL_TEXT)
    screen.blit(kill_text, kill_text.get_rect(topright=(WIDTH - 20, 18)))

    exp_text = font.render(f"EXP {player.exp}", True, COL_TEXT)
    screen.blit(exp_text, exp_text.get_rect(topright=(WIDTH - 20, 44)))


# =========================================================
# 7. ゲームオーバー画面
# =========================================================

def draw_gameover(screen, font_big, font, elapsed_ms, kills):
    """[拡張] リザルト画面: スコア集計・ハイスコア保存(ファイルI/O)は
       この画面を独立した状態として作り込む"""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    t1 = font_big.render("GAME OVER", True, (230, 80, 80))
    screen.blit(t1, t1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
    sec = elapsed_ms // 1000
    if jp_available():
        result_str = f"生存時間 {sec // 60:02d}:{sec % 60:02d}   撃破数 {kills}"
        hint_str = "Rキーでリスタート / ESCで終了"
    else:  # 日本語フォントが無い環境では英語表記（文字化け防止）
        result_str = f"TIME {sec // 60:02d}:{sec % 60:02d}   KILL {kills}"
        hint_str = "Press R to Restart / ESC to Quit"
    t2 = font.render(result_str, True, COL_TEXT)
    screen.blit(t2, t2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 5)))
    t3 = font.render(hint_str, True, (200, 200, 200))
    screen.blit(t3, t3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50)))


# =========================================================
# 1. メインループとゲーム状態管理
# =========================================================

def reset_game():
    """ゲーム開始/リスタート時の初期化。状態一式を dict で返す。"""# 修正: 剣・槍・斧の武器画像(fig/内のpng)を読み込む処理を追加
    img_sword = load_image("fig/sord01.png", (70, 70), (200, 200, 220))
    img_spear = load_image("fig/yari01.png", (100, 100), (180, 140, 90))
    img_axe = load_image("fig/ono.png", (55, 55), (150, 150, 160))
    return {
        "player": Player((WIDTH // 2, HEIGHT // 2)),
        "enemies": pygame.sprite.Group(),
        "bullets": pygame.sprite.Group(),# 修正: 剣・槍・斧などの近接攻撃スプライトを管理するグループを追加 追加実装(杉本)
        "attacks": pygame.sprite.Group(), # 修正: 3武器(剣・槍・斧)をweaponsリストに登録　追加実装(杉本)
        "weapons": [Weapon(),
                    SwordWeapon(img_sword),
                    SpearWeapon(img_spear),
                    AxeWeapon(img_axe)],
        "items": pygame.sprite.Group(),
        "start_ms": pygame.time.get_ticks(),
        "last_spawn": 0,
        "kills": 0,
    }


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("生きのこれ！こうかとん")
    clock = pygame.time.Clock()
    font = load_font(22)
    font_big = load_font(64)

    game = reset_game()
    state = "PLAY"  # PLAY / GAMEOVER
    # [拡張] タイトル画面・ポーズ・レベルアップ選択画面は
    #        state に "TITLE" / "PAUSE" / "LEVELUP" を追加して分岐する
    final_time = 0

    while True:
        now = pygame.time.get_ticks()

        # --- イベント処理 ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if state == "GAMEOVER" and event.key == pygame.K_r:
                    game = reset_game()
                    state = "PLAY"

        # --- 更新処理 ---
        if state == "PLAY":
            player = game["player"]
            enemies = game["enemies"]
            bullets = game["bullets"]
            elapsed = now - game["start_ms"]

            keys = pygame.key.get_pressed()
            player.update(keys, now)

            # 敵スポーン
            if now - game["last_spawn"] >= SPAWN_INTERVAL:
                spawn_enemy(enemies, elapsed)
                game["last_spawn"] = now

            enemies.update(player)
            for weapon in game["weapons"]:
                weapon.update(now, player, enemies, bullets, game["attacks"])
            bullets.update()
            game["attacks"].update(now)   # 追加実装(杉本)

            # --- 5. 当たり判定 ---
            # 弾 × 敵
            hits = pygame.sprite.groupcollide(bullets, enemies, True, False)
            for bullet, hit_enemies in hits.items():
                for enemy in hit_enemies:
                    if enemy.take_damage(bullet.damage):
                        game["kills"] += 1
            for attack in game["attacks"]:# 修正: 近接攻撃(剣・槍・斧) × 敵 の当たり判定を追加hit_ids で「同じ敵には1回だけ当たる」貫通型にしている　追加実装(杉本)
                for enemy in pygame.sprite.spritecollide(attack, enemies, False):
                    if id(enemy) in attack.hit_ids:
                        continue
                    attack.hit_ids.add(id(enemy))
                    if enemy.take_damage(attack.damage):
                        game["kills"] += 1
                        spawn_item_drop(enemy.rect.center, game["items"])

            # 敵 × プレイヤー
            touched = pygame.sprite.spritecollide(player, enemies, False)
            if touched:
                player.take_damage(touched[0].damage, now)
                if player.hp <= 0:
                    final_time = elapsed
                    state = "GAMEOVER"
            # プレイヤー × アイテム（触れると消えて回復/EXP加算）
            collect_items(player, game["items"])

        # --- 描画処理 ---
        screen.fill(COL_BG)
        if state == "PLAY":
            game["bullets"].draw(screen)
            game["attacks"].draw(screen)
            game["enemies"].draw(screen)
            game["items"].draw(screen)
            game["player"].draw(screen, now)
            draw_hud(screen, font, game["player"],
                     now - game["start_ms"], game["kills"])
        else:  # GAMEOVER
            game["bullets"].draw(screen)
            game["attacks"].draw(screen)
            game["enemies"].draw(screen)
            game["items"].draw(screen)
            draw_hud(screen, font, game["player"], final_time, game["kills"])
            draw_gameover(screen, font_big, font, final_time, game["kills"])
           
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()