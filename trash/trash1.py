import argparse
import inspect
import itertools as it
import math
import operator
import random
import re
import string
from collections import UserDict, UserList, defaultdict, namedtuple
from functools import partial
from operator import methodcaller
from pathlib import Path

import pygame as pg

EVENT_HANDLER_PREFIX = 'on_'

class AttrDict(UserDict):

    def __getitem__(self, name):
        return getattr(self, name)

    def __setitem__(self, name, value):
        setattr(self, name, value)

    def __delitem__(self, name):
        delattr(self, name)


class Word:

    def __init__(self, text):
        self.text = text
        self.initial = text

    def __len__(self):
        return len(self.text)

    def __hash__(self):
        return hash(self.text)

    def __bool__(self):
        return bool(self.text)

    def __getitem__(self, index):
        return self.text[index]

    def __eq__(self, other):
        if isinstance(other, Word):
            return self.text == other.text
        else:
            return self.text == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.text < other

    def __le__(self, other):
        return self.text <= other

    def __gt__(self, other):
        return self.text > other

    def __ge__(self, other):
        return self.text >= other


class TypingGame:

    def __init__(self, vocabulary, minlength=3, maxlength=6):
        self.vocabulary = [Word(word) for word in vocabulary]
        self.minlength = minlength
        self.maxlength = maxlength
        self.current = []
        self.lock = None

    def allowable(self):
        return list(word for word in self.vocabulary
                         if self.minlength <= len(word) <= self.maxlength)

    def spawn(self, nwords):
        """
        Return a list, length `nwords`, of randomly selected words from `vocabulary`.
        """
        # avoiding `set` and using `shuffle` to maintain predictable results
        # when `random.seed` is set manually, for tests.

        # it would be impossible to find more than 26 words starting with
        # unique letters
        assert nwords <= 26, f'nwords {nwords}, is greater than 26.'
        soup = [word for word in self.allowable() if word not in self.current]
        random.shuffle(soup)
        spawned = []
        while len(spawned) < nwords:
            firstletters = set(existing[0] for existing in spawned)
            for word in soup:
                if word[0] not in firstletters:
                    break
            else:
                # XXX: what to do when a word can't be found?
                raise RuntimeError
            spawned.append(word)
            soup.remove(word)
        return spawned

    def shoot(self, letter):
        assert len(letter) == 1

        if self.lock is not None and not self.lock.text:
            self.lock = None

        if self.lock is None:
            # try to find a new lock
            for word in self.current:
                if word and word[0] == letter:
                    self.lock = word
                    break
            else:
                self.lock = None

        if self.lock is not None and letter == self.lock.text[0]:
            self.lock.text = self.lock.text[1:]
        else:
            self.lock = None

        return self.lock


def lerp(a, b, t):
    return (1 - t) * a + t * b

def lerpiter(a, b, timestep):
    t = 0
    while t <= 1:
        yield lerp(a, b, t)
        t += timestep
    if t > 1:
        yield lerp(a, b, 1)

def lerps(itera, iterb, t):
    """
    Handle `lerp`ing iterables together.
    """
    # no idea what to name this function
    return tuple(lerp(a, b, t) for a, b, in zip(itera, iterb))

def lerpsiter(itera, iterb, timestep):
    t = 0
    while t <= 1:
        yield lerps(itera, iterb, t)
        t += timestep
    if t > 1:
        yield lerps(itera, iterb, 1)

class Global:

    game = None
    screen = None
    clock = None
    group = None
    states = None
    camera = None
    assets = AttrDict({
        "png": defaultdict(list)
    })

    padding = None


g = Global()

def randomrect(rect, inside):
    rect = rect.copy()
    right = inside.right - rect.width
    if right < inside.left:
        right = inside.left
    x = random.randint(inside.left, right)
    bottom = inside.bottom - rect.height
    if bottom < inside.top:
        bottom = inside.top
    y = random.randint(inside.top, bottom)
    rect.topleft = (x, y)
    return rect

class Surface(pg.Surface):

    def __init__(self, size, flags=pg.SRCALPHA):
        super().__init__(size, flags)


class Color(pg.Color):

    def __init__(self, *args, alpha=255):
        super().__init__(*args)
        self.a = alpha


class Font:

    def __init__(self, *args):
        self._font = pg.font.Font(*args)

    def render(self, *args):
        images = []
        for line in args[0].splitlines():
            images.append(self._font.render(line, *args[1:]))
        get_size = methodcaller('get_size')
        widths, heights = zip(*map(get_size, images))
        result = Surface((max(widths), sum(heights)))
        y = 0
        for image in images:
            result.blit(image, (0, y))
            y += image.get_height()
        return result

class Screen:

    def __init__(self, size, background=None):
        self.image = pg.display.set_mode(size)
        self.rect = Rect(self.image.get_rect())
        if background is None:
            background = self.image.copy()

        if background.get_size() != self.rect.size:
            background = pg.transform.scale(background, self.rect.size)

        self.background = background
        self.image.blit(background, (0,0))


class Clock:

    def __init__(self, framerate):
        self.framerate = framerate
        self.dt = None
        self._clock = pg.time.Clock()

    def tick(self):
        self.dt = self._clock.tick(self.framerate)
        return self.dt


class Rect(pg.Rect):

    def copy(self, **attrs):
        rect = super().copy()
        for key, value in attrs.items():
            setattr(rect, key, value)
        return rect


def renderbackground(size):
    tiles = list(image for name, image in g.assets["png"].items()
                       if name.startswith('starsbackground'))
    assert tiles
    twidth, theight = tiles[0].get_size()

    width, height = size
    background = Surface(size)

    for y in range(0, height * 2, theight):
        for x in range(0, width, twidth):
            background.blit(random.choice(tiles), (x, y))

    return background

class Group(pg.sprite.LayeredUpdates):

    def alive(self):
        return any(sprite.alive() for sprite in self.sprites())

    def boundingrect(self, **attrs):
        rects = [sprite.rect for sprite in self.sprites()]
        lefts, tops, rights, bottoms = zip(*
                (rect.topleft + rect.bottomright for rect in rects))
        left = min(lefts)
        top = min(tops)
        bounding = Rect(left, top, max(rights) - left, max(bottoms) - top)
        for name, value in attrs.items():
            assert hasattr(bounding, name)
            setattr(bounding, name, value)
        return bounding

    def moveasone(self, rect):
        br = self.boundingrect()
        ox, oy = rect.x - br.x, rect.y - br.y
        for sprite in self.sprites():
            sprite.rect.move_ip(ox, oy)

    def moveasone2(self, **attrs):
        br = self.boundingrect()
        for key, value in attrs.items():
            setattr(br, key, value)
        self.moveasone(br)


class Sprite(pg.sprite.Sprite):

    def kill(self):
        super().kill()
        callback = getattr(self, 'on_kill', None)
        if callback is not None:
            callback(self)


class ScrollSprite(Sprite):

    speed = 16
    theight = None
    inside = None

    def update(self):
        if self.theight is None:
            self.theight = next(image.get_height()
                                for image in g.assets["png"]["starsbackground"])
        self.rect.bottom = (self.rect.bottom + self.speed) % self.inside.height


class LockedSprite(Sprite):

    def __init__(self, lockto, attr1, attr2, *groups):
        super().__init__(*groups)
        self.lockto = lockto
        self.attr1 = attr1
        self.attr2 = attr2

    def update(self):
        setattr(self.rect, self.attr1, getattr(self.lockto.rect, self.attr2))


class WaveText(Sprite):

    def __init__(self, text, *groups):
        super().__init__(*groups)
        font = Font(None, int(min(g.screen.rect.size)/3))
        self.image = font.render(text, True, Color('white'))
        self.rect = Rect(self.image.get_rect())


def wavetextanimationiter(sprite, step):
    centered = sprite.rect.copy(center=g.screen.rect.center)
    return it.chain(
        # delay
        lerpsiter(
            sprite.rect.copy(midbottom=g.screen.rect.midtop),
            sprite.rect.copy(midbottom=g.screen.rect.midtop),
            step
        ),
        # top to center
        lerpsiter(
            sprite.rect.copy(midbottom=g.screen.rect.midtop),
            centered,
            step
        ),
        # delay
        lerpsiter(
            centered,
            centered,
            step / 4
        ),
        # center to bottom
        lerpsiter(
            centered,
            sprite.rect.copy(midtop=g.screen.rect.midbottom),
            step
        ),
    )

class Laser(Sprite):

    def __init__(self, target, *groups):
        super().__init__(*groups)
        self.target = target
        self._image = self.image = random.choice(g.assets["png"]["laser"])
        self.rect = Rect(self.image.get_rect())
        self.t = 0

    def update(self):
        self.rect.center = lerps(self.rect.center, self.target.rect.center, self.t)
        if self.t == 0:
            self.t += .1

        dx, dy = (self.target.rect.centerx - self.rect.centerx,
                  self.target.rect.centery - self.rect.centery)
        angle = math.degrees(math.atan2(-dy, dx))
        self.image = pg.transform.rotate(self._image, angle)

        if self.rect.colliderect(self.target.rect):
            self.kill()


class Explosion(Sprite):

    def __init__(self, *groups):
        super().__init__(*groups)
        self.t = 0
        self.timestep = .02

        self.angle1 = random.choice(range(360))
        while True:
            self.angle2 = self.angle1 + random.choice(range(-30, 30))
            if abs(self.angle2) >= 15:
                break

        self.scale1 = 0
        self.scale2 = .25

        self._image = g.assets["png"]["explosion"][0]
        self.rect = self._image.get_rect()
        self.rotscale()

    def rotscale(self):
        self.image = pg.transform.rotate(
            self._image,
            lerp(self.angle1, self.angle2, self.t)
        )
        self.image = pg.transform.scale(
            self.image,
            tuple(
                map(
                    lambda x: int(x * lerp(self.scale1, self.scale2, self.t)),
                    self.image.get_size()
                )
            )
        )
        self.rect = Rect(self.image.get_rect(center=self.rect.center))

    def update(self):
        self.rotscale()
        self.t += self.timestep
        if self.t >= 1:
            self.kill()


class Player(Sprite):

    def __init__(self, *groups):
        super().__init__(*groups)
        self.image = random.choice(g.assets.png["player"])
        self._image = self.image.copy()
        self.rect = self.image.get_rect()

        # relative to the center in screen space
        x = 40
        self.cannonoffsets = [(-x, -62), (x, -62)]
        self.cannon = 0

    def shoot(self, target):
        dx = target.rect.centerx - self.rect.centerx
        dy = target.rect.centery - self.rect.centery
        angle = math.atan2(-dy, dx)
        self.image = pg.transform.rotate(
            self._image,
            math.degrees(
                # the player image is pointing up, unrotate it by 90
                # degrees.
                angle - (math.pi / 2)))
        self.rect = Rect(self.image.get_rect(center=self.rect.center))

        cx, cy = self.cannonoffsets[self.cannon]
        self.cannon = (self.cannon + 1) % len(self.cannonoffsets)

        laser = Laser(target)
        x, y = g.player.rect.center
        radius = g.player.rect.height
        laser.rect.midbottom = (x + cx + math.cos( angle) * radius,
                                y + cy + math.sin(-angle) * radius)
        return laser


class Enemy(Sprite):
    pass


class EnemyShip(Enemy):

    def __init__(self, *groups):
        super().__init__(*groups)
        x = min(g.screen.rect.size)
        self.image = random.choice(g.assets.png["enemy"])
        self.rect = Rect(self.image.get_rect())
        self.x, self.y = None, None

    def update(self, *args):
        if self.x is None:
            self.x = self.rect.x
        if self.y is None:
            self.y = self.rect.y
        dx, dy = g.player.rect.centerx - self.x, g.player.rect.centery - self.y
        length = math.hypot(dx, dy)
        if length != 0:
            dx /= length
            dy /= length
        self.x += dx
        self.y += dy
        self.rect.centerx = self.x
        self.rect.centery = self.y


class LetterSprite(Enemy):

    def __init__(self, ship, letter, *groups):
        super().__init__(*groups)
        self.ship = ship
        self.letter = letter
        font = Font(None, int(min(g.screen.rect.size)/12))
        self.image = font.render(self.letter, True, Color('white'))
        self.rect = self.image.get_rect()
        self.offset = None
        self.update_offset()
        self._layer = 9

    def update_offset(self):
        self.offset = (self.rect.x - self.ship.rect.x,
                       self.rect.y - self.ship.rect.y)

    def update(self, *args):
        ox, oy = self.offset
        self.rect.topleft = (self.ship.rect.x + ox,
                             self.ship.rect.y + oy)


class ShadeSprite(Sprite):

    def __init__(self, rect, lockto, *groups):
        super().__init__(*groups)

        self.image = Surface(rect.size)
        self.image.fill(Color('black', alpha=190))
        self.rect = rect.copy()
        self._layer = 8

        self.lockto = lockto
        self.offset = None
        self.update_offset()

    def update_offset(self):
        self.offset = (self.lockto.rect.x - self.rect.x,
                       self.lockto.rect.y - self.rect.y)

    def update(self, *args):
        self.rect.topleft = (self.lockto.rect.x - self.offset[0],
                             self.lockto.rect.y - self.offset[1])


class LetterGroup(Group):

    def __init__(self, ship, letters, *sprites):
        super().__init__(*sprites)
        self.ship = ship
        self.letters = letters
        self.lettersprites = []

        # TODO: move `.shade` in other places of code
        pad = g.padding // 4

        # have to add sprites first to get a bounding rect
        x = 0
        for letter in self.letters:
            sprite = LetterSprite(self.ship, letter)
            sprite.rect.x = x
            x += sprite.rect.width
            self.add(sprite)
            self.lettersprites.append(sprite)

        paddedbounding = (
            self.boundingrect()
                .inflate(pad, pad)
                .copy(midtop = self.ship.rect.midbottom)
        )
        self.shade = ShadeSprite(paddedbounding, self.ship)

        align = self.boundingrect().copy(center = paddedbounding.center)
        x, y = align.topleft

        # TODO: lettersprites attribute not needed so long as the group is ordered
        for lettersprite in self.lettersprites:
            lettersprite.rect.topleft = (x, y)
            x += lettersprite.rect.width
            lettersprite.update_offset()

        self.add(self.shade)


class EnemyGroup(Group):

    def __init__(self, word, *sprites):
        super().__init__(*sprites)
        self.word = word
        self.ship = EnemyShip()
        self.lettergroup = LetterGroup(self.ship, list(self.word), self)

        # NOTE: lettergroup needs to update first, to catch the intended,
        #       initial, offset from the ship.
        self.add(self.lettergroup, self.ship)


class StateStack(UserList):

    def append(self, state):
        if self:
            self[-1].exit()
        super().append(state)
        state.enter()

    def pop(self):
        state = super().pop()
        state.exit()
        if self:
            self[-1].enter()
        return state


class EventHandler:

    def __init__(self, method, enabled=True):
        self.method = method
        self.enabled = enabled

    def __call__(self, event):
        return self.method(event)


def get_event_method_name(event_type):
    return EVENT_HANDLER_PREFIX + pg.event.event_name(event_type)

class EventDispatcher:

    def __init__(self, obj):
        self.obj = obj
        self.handlers = {}
        self.update_handlers()

    def enable(self, text=EVENT_HANDLER_PREFIX):
        """
        Enable handlers with names starting with `text`. Disables all by default.
        """
        for name, handler in self.handlers.items():
            if name.startswith(text):
                handler.enabled = True

    def disable(self, text=EVENT_HANDLER_PREFIX):
        """
        Disable handlers with names starting with `text`. Disables all by default.
        """
        for name, handler in self.handlers.items():
            if name.startswith(text):
                handler.enabled = False

    def dispatch(self, event):
        method_name = get_event_method_name(event.type)
        if method_name in self.handlers and self.handlers[method_name].enabled:
            return self.handlers[method_name](event)

    def update_handlers(self):
        for name in dir(self.obj):
            attr = getattr(self.obj, name)
            if callable(attr) and name.startswith(EVENT_HANDLER_PREFIX):
                self.handlers[name] = EventHandler(attr)


class State:

    def __init__(self):
        self.methodstack = list()
        self.eventdispatcher = EventDispatcher(self)

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self):
        if self.methodstack:
            self.methodstack[-1]()


class Engine:

    def __init__(self, screensize, framerate=60, background=None,
                 debug_drawrects=False):
        """
        :param screensize: 2-tuple screen size.
        :param framerate: frames for per limit. default: 60.
        :param background: pygame Surface for background. default None, black.
        :param debug_drawrects: draw pink rects of each sprite's rect
                                attribute. default: False.
        """
        self.npass, self.nfail = pg.init()
        self.debug_drawrects = debug_drawrects
        self.running = False
        g.screen = Screen(screensize, background=background)
        g.camera = g.screen.rect.copy()
        g.clock = Clock(framerate)
        g.group = Group()
        g.states = StateStack()

        for path in Path("./assets/png").iterdir():
            base, *_ = re.split("\d+", path.stem)
            image = pg.image.load(str(path)).convert_alpha()
            g.assets.png[base].append(image)

        g.padding = min(g.screen.rect.size) / 12

    def run(self, states):
        try:
            for state in states:
                g.states.append(state)
        except TypeError:
            g.states.append(states)
        self.running = True
        while self.running:
            self.step()

    def step(self):
        g.clock.tick()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
                return
            else:
                g.states[-1].eventdispatcher.dispatch(event)
        g.states[-1].update()
        g.group.update()
        g.group.clear(g.screen.image, g.screen.background.subsurface(g.camera))
        dirty = g.group.draw(g.screen.image) or g.screen.rect
        if self.debug_drawrects:
            for sprite in g.group.sprites():
                pg.draw.rect(g.screen.image, Color("pink"), sprite.rect, 1)
        pg.display.update(dirty)


class SimpleSprite(Sprite):

    def __init__(self, *groups):
        super().__init__(*groups)
        self.image = Surface((64, 64))
        self.image.fill(Color('red'))
        self.rect = self.image.get_rect()


class LoaderState(State):

    def enter(self):
        self.screenbackup = g.screen.image.copy()
        self.frameratebackup = g.clock.framerate
        g.clock.framerate = math.inf

        font = Font(None, int(min(g.screen.rect.size) / 12))
        image = font.render("Loading...", True, Color('white'))
        g.screen.image.blit(image, image.get_rect(center=g.screen.rect.center))

        self.countdown = 3
        self.methodstack.append(self.update)

    def update(self):
        pg.display.update(g.screen.rect)
        self.countdown -= 1
        if self.countdown == 0:
            self.methodstack.pop()
            g.states.pop()
        import time
        time.sleep(1)

    def exit(self):
        g.clock.framerate = self.frameratebackup
        g.screen.image = self.screenbackup


class SimpleTestState(State):

    def enter(self):
        sprite = SimpleSprite()
        sprite.rect = sprite.image.get_rect(center=g.screen.rect.center)
        g.group.add(sprite)

        font = Font(None, int(min(g.screen.rect.size) / 12))
        message = Sprite()
        message.image = font.render("There should be a red box\n"
                                    "in the middle of the screen.",
                                    True, Color('white'))
        message.rect = message.image.get_rect(midtop=g.screen.rect.midtop)
        g.group.add(message)

    def on_KeyDown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))


def current_player():
    return getattr(g, 'player', None)

def current_player_or_new():
    sprite = current_player() or Player()
    sprite._layer = 1
    return sprite


def background_sprites():
    tiles = g.assets.png["starsbackground"]
    random.shuffle(tiles)
    i = 0

    twidth, theight = tiles[0].get_size()
    ScrollSprite.inside = g.screen.rect.copy(
            height = g.screen.rect.height + theight)

    sprites = []
    for x in range(0, g.screen.rect.width, twidth):
        for y in range(-theight, g.screen.rect.height, theight):
            sprite = ScrollSprite()
            sprite.image = tiles[i]
            sprite.rect = sprite.image.get_rect(x=x, y=y)
            sprites.append(sprite)

            i += 1
            if i == len(tiles):
                random.shuffle(tiles)
                i = 0
    return sprites

class GameplayState(State):

    def __init__(self):
        super().__init__()
        player = current_player_or_new()
        player.rect.midbottom = g.screen.rect.midtop
        g.player = player
        g.group.add(player)

        self.t = 0
        self.enemygroups = []
        self.laser2lettersprite = {}

        self.ship2explosions = defaultdict(list) # ship: list of explosions
        self.lettersprite2enemygroup = {}
        self.word2enemygroup = {}
        self.lettersprite2word = {}

        self.wave = 1
        self.wavetextsprite = None
        self.wavelerpsiter = None

        g.group.add(*background_sprites())

    def enter(self):
        # TODO: LoaderState class for loading screen.
        #
        self.eventdispatcher.disable('on_KeyDown')
        self.methodstack.append(self.playing)
        self.methodstack.append(self.spawn)
        self.methodstack.append(self.intro_wave)
        self.methodstack.append(self.intro)

    def playing(self):
        # removing dead explosions
        for ship, explosions in self.ship2explosions.items():
            remove = []
            for explosion in explosions:
                if not explosion.alive():
                    remove.append(explosion)
            for explosion in remove:
                self.ship2explosions[ship].remove(explosion)

        # check for enemy groups without any letters
        remove = []
        for enemygroup in self.enemygroups:
            if (# no letter sprites left alive
                not any(isinstance(sprite, LetterSprite) and sprite.alive()
                        for sprite in enemygroup.sprites())
                # no other explosions playing
                and (enemygroup.ship in self.ship2explosions
                     and not self.ship2explosions[enemygroup.ship])
            ):
                remove.append(enemygroup)
                for sprite in enemygroup.sprites():
                    sprite.kill()
                # Big Explosion for ship
                explosion = Explosion()
                explosion.rect.center = enemygroup.ship.rect.center
                explosion.scale2 = 2
                explosion.timestep = .025
                explosion.rotscale()
                g.group.add(explosion)
                enemygroup.add(explosion)
                self.ship2explosions[sprite].append(explosion)

        for enemygroup in remove:
            self.enemygroups.remove(enemygroup)
        if (not self.has_enemies()
                and not any(isinstance(sprite, Explosion) and sprite.alive()
                            for sprite in g.group.sprites())):
            self.wave += 1
            self.methodstack.append(self.spawn)
            self.methodstack.append(self.intro_wave)

        # check laser2lettersprite dead sprites
        remove = []
        for laser, sprite in self.laser2lettersprite.items():
            if not sprite.alive():
                remove.append(laser)
        for laser in remove:
            del self.laser2lettersprite[laser]

    def intro_wave(self):
        if self.wavetextsprite is not None:
            self.wavetextsprite.kill()
            self.methodstack.pop()
            self.wavetextsprite = None
        else:
            self.wavetextsprite = WaveText(f'WAVE {self.wave}')
            self.wavetextsprite._layer = 9
            self.wavelerpsiter = wavetextanimationiter(self.wavetextsprite, .05)
            self.t = 0
            self.methodstack.append(self.intro_wave_update)

    def intro_wave_update(self):
        try:
            x, y, width, height = next(self.wavelerpsiter)
        except StopIteration:
            self.methodstack.pop()
        else:
            g.group.add(self.wavetextsprite)
            self.wavetextsprite.rect.topleft = (x, y)

    def intro(self):
        if self.t <= 1:
            g.player.rect.midbottom = lerps(
                    g.screen.rect.midtop,
                    g.screen.rect.midbottom,
                    self.t)
            self.t += .025
        else:
            self.eventdispatcher.enable('on_KeyDown')
            self.methodstack.pop()

    def spawn(self):
        spawned_words = g.game.spawn(5)
        g.game.current.extend(spawned_words)
        g.game.current.extend(spawned_words)

        spawnrect = g.screen.rect.copy()
        spawnrect.height /= 2
        spawnrect.midbottom = g.screen.rect.midtop

        for word in spawned_words:
            enemygroup = EnemyGroup(word)

            # randomly position the group
            while True:
                position = randomrect(enemygroup.boundingrect(), spawnrect)
                # generate until not colliding
                if not any(position.colliderect(sprite.rect)
                           for sprite in g.group.sprites()
                           if isinstance(sprite, Enemy)):
                    enemygroup.moveasone(position)
                    break

            # fast lookups
            self.word2enemygroup[word] = enemygroup
            for lettersprite in enemygroup.lettergroup.sprites():
                self.lettersprite2enemygroup[lettersprite] = enemygroup
                self.lettersprite2word[lettersprite] = word

            self.enemygroups.append(enemygroup)
            g.group.add(enemygroup)

        self.methodstack.pop()

    def has_enemies(self):
        return bool(self.enemygroups)

    def is_playing(self):
        """
        """
        return self.methodstack and self.methodstack[-1] == self.playing

    def shoot(self, letter):
        word = g.game.shoot(letter)
        if word is not None:
            # find the ship to target
            for enemygroup in self.enemygroups:
                if enemygroup.word.initial == word.initial:
                    target = enemygroup.ship
                    for sprite in enemygroup.lettergroup.lettersprites:
                        if (sprite not in self.laser2lettersprite.values()
                                and sprite.alive()
                                and sprite.letter == letter):
                            lettersprite = sprite
                            break
                    else:
                        raise RuntimeError("Unable to find letter sprite.")
                    break
            else:
                raise RuntimeError("Unable to find ship to target.")

            laser = g.player.shoot(target)
            g.group.add(laser)
            laser.on_kill = self.on_laser_killed
            self.laser2lettersprite[laser] = lettersprite

    def on_laser_killed(self, laser):
        # find the EnemyGroup lettersprite belongs to then kill it and see if
        # that was the last letter sprite, if it was kill the shade sprite
        lettersprite = self.laser2lettersprite[laser]
        enemygroup = self.lettersprite2enemygroup[lettersprite]
        if lettersprite in enemygroup.lettergroup:
            lettersprite.kill()
            if not any(isinstance(sprite, LetterSprite) and sprite.alive()
                       for sprite in enemygroup.sprites()):
                enemygroup.lettergroup.shade.kill()
        # make an explosion where lettersprite's target was
        explosion = Explosion()
        explosion.rect.center = laser.target.rect.center
        g.group.add(explosion)
        self.ship2explosions[laser.target].append(explosion)

    def on_KeyDown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))
        elif (self.is_playing()
                and event.unicode in string.ascii_lowercase):
            self.shoot(event.unicode)


def repeated_letters(word):
    return all(letter == word[0] for letter in word)

def wordfilter(word):
    return not repeated_letters(word)

def getwords():
    strip = methodcaller('strip')
    with open("assets/words.txt") as words_file:
        return list(word
                    for word in map(strip, words_file.readlines())
                    if wordfilter(word))

def testlerp():
    assert lerp(0, 1, .5) == .5
    assert lerp(-1, 1, .5) == 0

    assert lerps((0,0), (1,1), .5) == (.5, .5)
    assert lerps((0,0), (0,1), .5) == (0, .5)

def testword():
    words = [Word('bruce'), Word('config'), Word('gentle')]
    assert 'bruce' in words
    assert 'tainted' not in words

    words[-1].text = words[-1].text[1:]
    assert words[-1].text == entle

def testgame():
    words = getwords()
    random.seed(0)
    game = TypingGame(words, 3, 8)

    nwords = 26
    game.current.extend(game.spawn(nwords))
    assert len(game.current) == nwords
    assert len(set(game.current)) == len(game.current)

    assert sorted(game.current) == ['achieved', 'bios', 'chamber', 'decision',
                                    'emission', 'figure', 'growing', 'hull',
                                    'invited', 'jason', 'kidney', 'lat',
                                    'midi', 'nights', 'offer', 'photo',
                                    'quote', 'restrict', 'sms', 'tree', 'unit',
                                    'vector', 'writers', 'xml', 'yard',
                                    'zealand']

    word = game.shoot('b')
    assert word.initial == 'bios'
    assert word.text == 'ios'

    word = game.shoot('z')
    assert word is None

    word = game.shoot('i')
    assert word.initial == 'bios'
    assert word.text == 'os'

    game.shoot('o')
    word = game.shoot('s')
    assert word.text == ''
    assert word.initial == 'bios'
    assert word.text == ''

    word = game.shoot('a')
    assert word.text == 'chieved'
    assert word.initial == 'achieved'

    for letter in 'chieve':
        word = game.shoot(letter)
    assert word.text == 'd'
    assert word.initial == 'achieved'

    word = game.shoot('d')
    assert word.text == ''

    word = game.shoot('g')
    # now there are several 'r's exposed

    word = game.shoot('r')
    #print(word, word.initial, word.text)

    #print(list(word.text for word in game.current))

    random.seed()

def tests():
    testlerp()
    testgame()

def main():
    """
    ZPype: ZType clone.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--no-run', action='store_true', help='Just tests no game.')
    args = parser.parse_args()

    tests()

    if args.no_run:
        return

    size = (500,1000)
    g.game = TypingGame(getwords())
    engine = Engine(size)

    engine.run([GameplayState()])
    #engine.run([GameplayState(), LoaderState()])

if __name__ == '__main__':
    main()
