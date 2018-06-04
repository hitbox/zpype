import argparse
import inspect
import itertools as it
import logging
import math
import random
from collections import OrderedDict, UserDict, UserList, defaultdict, deque
from pathlib import Path

import pygame as pg

tau = math.pi * 2

MODULENAME = Path(__file__).stem

SCREENSIZE = (500, 1000)
FRAMERATE = 60
FONTSIZE = 32
PAD = 10

TYPE2NAME = {eventtype: pg.event.event_name(eventtype).upper()
              for eventtype in range(pg.NOEVENT, pg.NUMEVENTS)
              if pg.event.event_name(eventtype) not in ('Unknown',)}
EVENT_METHOD_PREFIX = "on_"

BIG_SHIP = (64, 32)
SMALL_SHIP = (32, 32)

SHIP_CHOICES = list()
SHIP_CHOICES.extend((SMALL_SHIP, ) * 10)
SHIP_CHOICES.extend((BIG_SHIP, ) * 1)

def loggername(inst):
    return '.'.join([MODULENAME, inst.__class__.__name__])

def getlogger(inst):
    logger = logging.getLogger(loggername(inst))
    for f in logger.parent.filters:
        logger.addFilter(f)
    return logger

def scaled(iter, x):
    return tuple(v * x for v in iter)

class util:

    @staticmethod
    def lerp(a, b, t):
        return (1 - t) * a + t * b

    @staticmethod
    def sinlerp(a, b, t):
        f = math.sin(t * math.pi / 2)
        return (1 - f) * a + f * b

    @staticmethod
    def coslerp(a, b, t):
        f = (1 - math.cos(t * math.pi / 2))
        return a * (1 - f) + b * f

    @staticmethod
    def lerprange(a, b, step):
        t = 0
        while t <= 1:
            yield util.lerp(a, b, t)
            t += step

    @staticmethod
    def lerpiter(a, b, duration, lerpfunc=None):
        if lerpfunc is None:
            lerpfunc = util.lerp
        time = 0
        while time <= duration:
            value = lerpfunc(a, b, time / duration)
            yield value
            time += g.dt / 1000
        if time != duration:
            yield lerpfunc(a, b, 1)

    @staticmethod
    def lerpsiter(seq1, seq2, duration, lerpfunc=None):
        iters = list(util.lerpiter(a, b, duration, lerpfunc) for a, b in zip(seq1, seq2))
        running = set(iters)
        while running:
            values = deque()
            for index, iterator in enumerate(iters):
                try:
                    value = next(iterator)
                except StopIteration:
                    running.remove(iterator)
                    iters[index] = it.repeat(value)
                    value = next(iters[index])
                finally:
                    values.append(value)
            if running:
                yield tuple(values)


def get_event_method(inst, event_type, fallback=None):
    """
    """
    return getattr(inst, EVENT_METHOD_PREFIX + TYPE2NAME[event_type], fallback)

def deltato(pos1, pos2, speed=1):
    """
    Return normalized vector from `pos1` to `pos2`, multiplied by `speed` as a
    two-tuple.
    """
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    length = math.sqrt(dx * dx + dy * dy)
    if abs(length) > 0:
        dx /= length
        dy /= length
        return (dx * speed, dy * speed)
    return (0, 0)

class draw:

    @staticmethod
    def circle(surface, color, position, radius, width=0):
        """
        pygame.draw.circle supporting better width rendering.
        """
        if width == 0:
            return pg.draw.circle(surface, color, position, radius, width)
        pg.draw.circle(surface, color, position, radius, 0)
        color = Color(*tuple(color))
        color.a = 0
        return pg.draw.circle(surface, color, position, radius - width, 0)


class Game:

    def __init__(self, words, maxspawn, minletters=3, maxletters=6):
        self.dictionary = defaultdict(list)
        for word in words:
            self.dictionary[len(word)].append(word)
        self.maxspawn = maxspawn
        self.minletters = minletters
        self.maxletters = maxletters

        self.active_words = []
        self.typing_at = None

    def find(self, letter):
        """
        Return the already locked word, or the first word starting with `letter`.
        """
        for word in self.active_words:
            if word.startswith(letter):
                return word

    def hit_word(self, word):
        """
        Strip first letter from word, updating active_words, returning the new word.
        """
        index = self.active_words.index(word)
        self.active_words[index] = self.active_words[index][1:]
        if self.active_words[index] == '':
            self.active_words.pop(index)
            return None
        return self.active_words[index]

    def spawn(self, nletters):
        """
        Return a random word of length nletters from dictionary.
        """
        return random.choice(self.dictionary[nletters])

    def spawnmax(self):
        while len(self.active_words) < self.maxspawn:
            nletters = random.randint(self.minletters, self.maxletters)
            word = self.spawn(nletters)
            if (word not in self.active_words
                    and not any(existing.startswith(word[0])
                                for existing in self.active_words)):
                self.active_words.append(word)


class Event:

    def __new__(self, type, **attrs):
        attrs.update(type=type)
        return pg.event.Event(type, **attrs)


class Screen:

    def __init__(self, size):
        self.image = pg.display.set_mode(size)
        self.rect = Rect(self.image.get_rect())
        self.background = self.image.copy()


class Clock:

    def __init__(self, framerate):
        self.framerate = framerate
        self._clock = pg.time.Clock()

    def tick(self):
        return self._clock.tick(self.framerate)


class Color(pg.Color):

    def __init__(self, *args, alpha=255):
        super().__init__(*args)
        self.a = alpha


class Driver:

    def __init__(self):
        self.iterable = iter(tuple())
        self.attr = 'center'

    def run(self, iterable, attr=None):
        if attr is not None:
            self.attr = attr
        self.iterable = iterable

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.iterable)


class Rect(pg.Rect):

    def __init__(self, *args):
        super().__init__(*args)
        self.driver = Driver()

    def copy(self, *args, **kwargs):
        rect = Rect(super().copy())
        modifiers = OrderedDict(args)
        modifiers.update(kwargs)
        for key, value in modifiers.items():
            attr = getattr(rect, key)
            if callable(attr):
                rv = attr(*value)
                if isinstance(rv, pg.Rect):
                    rect = rv
            else:
                setattr(rect, key, value)
        return rect

    def random(self, inside):
        # XXX: clamping here because `self.width` and `self.height` might make
        #      `b` for `random.randint` less than `a`. there's probably a
        #      better way.
        x = random.randint(inside.left, inside.right)
        y = random.randint(inside.top, inside.bottom)
        rect = self.copy(topleft=(x,y))
        return Rect(rect.clamp(inside))

    def update(self):
        if self.driver.iterable:
            try:
                value = next(self.driver)
            except StopIteration:
                self.driver.iterable = None
            else:
                setattr(self, self.driver.attr, value)


class Surface(pg.Surface):

    def __init__(self, size, flags=pg.SRCALPHA):
        super().__init__(size, flags)

    def get_rect(self, **attrs):
        return Rect(super().get_rect(**attrs))


class Group(pg.sprite.LayeredDirty):

    def allgroups(self):
        """
        Return a set of all groups.
        """
        found = set()
        groups = []
        for sprite in g.sprites.sprites():
            for group in sprite.groups():
                if group not in found:
                    found.add(group)
                    groups.append(group)
        return groups

    def boundingrect(self):
        if len(self):
            rects = [sprite.rect for sprite in self.sprites()]
            x, y = (min(rect.left for rect in rects),
                    min(rect.top for rect in rects))
            width = max(rect.right for rect in rects) - x
            height = max(rect.bottom for rect in rects) - y
            return Rect(x, y, width, height)

    def position(self, rect):
        _rect = self.boundingrect()
        if _rect:
            ox, oy = rect.x - _rect.x, rect.y - _rect.y
            for sprite in self.sprites():
                sprite.rect.move_ip(ox, oy)
                # update x, y if exists
                try:
                    sprite.x = sprite.rect.centerx
                    sprite.y = sprite.rect.centery
                except AttributeError:
                    pass

    def positioned(self, *args, **kwargs):
        rect = self.boundingrect()
        if rect:
            self.position(rect.copy(*args, **kwargs))

    def update(self, *args):
        for sprite in g.sprites.sprites():
            if sprite.active:
                sprite.update(*args)


class EventHandler:

    def __init__(self, name, method, enabled=True):
        self.name = name
        self.method = method
        self.enabled = enabled
        self.logger = getlogger(self)

    def __bool__(self):
        return bool(self.method)

    def __call__(self, event):
        return self.method(event)

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def toggle(self):
        self.enabled = not self.enabled


class EventHandlerGroup(UserDict):

    def disable(self):
        for handler in self.values():
            handler.disable()

    def enable(self):
        for handler in self.values():
            handler.enable()

    def toggle(self):
        for handler in self.values():
            handler.toggle()

    @classmethod
    def from_instance(cls, inst):
        return cls({name: EventHandler(name, get_event_method(inst, type))
                    for type, name in TYPE2NAME.items()})


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


class State:

    def __init__(self):
        self.brain = list()
        self.eventhandlers = EventHandlerGroup.from_instance(self)
        self.logger = getlogger(self)
        self.saved_sprites = Group()

    def enter(self):
        """
        Add this state's sprites back to the global sprites.
        """
        # called by StateStack when appened to stack, or when this becomes the
        # topmost from a pop transitioning stuff must be done before this.
        self.logger.info('enter')
        for sprite in self.saved_sprites:
            g.sprites.add(sprite)

    def exit(self):
        """
        Remove this instance's sprites from global sprites, saving them.
        """
        # called by StateStack when popped or when an append makes this the
        # state underneath the topmost. transitioning state
        self.logger.info('exit')
        for sprite in self.saved_sprites.sprites():
            g.sprites.remove(sprite)
            self.saved_sprites.add(sprite)

    def update(self, *args):
        if self.brain:
            method = self.brain[-1]
            if method:
                method()


class MainmenuState(State):
    """
    Introduce player and present main menu.
    """
    def __init__(self):
        super().__init__()
        self.logo = LogoSprite("ZPype", 6)
        self.logo.rect.center = g.screen.rect.center

        self.play = LogoSprite("Enter to play", 2)
        self.quit = LogoSprite("Escape to quit", 2)

        rect = self.play.image.get_rect()

        self.play.rect.top = self.logo.rect.move(0, PAD).bottom
        self.quit.rect.top = self.play.rect.move(0, PAD).bottom
        g.sprites.add(g.player, self.logo, self.play, self.quit)

        self.slide = g.screen.rect.inflate(g.screen.rect.width*8,0)

    def enter(self):
        super().enter()
        self.eventhandlers.enable()
        self.intro_init()

    def intro_init(self):
        self.logger.info('intro_init')
        duration = 1
        # slide the logo in from the right
        rect = self.logo.rect
        # NOTE: saving final position of logo because when we reenter this
        #       function, logo will have been positioned somewhere else and
        #       we're using it to position the player.
        logofinal = rect.copy(centerx=self.slide.centerx)
        rect.driver.run(
            util.lerpsiter(
                rect.copy(right=self.slide.right).midleft,
                logofinal.midleft,
                duration
            ),
            attr='midleft'
        )
        # slide "play" in from left to center
        self.play.rect.driver.run(
            util.lerpsiter(
                self.play.rect.copy(left=self.slide.left).midleft,
                self.play.rect.copy(centerx=self.slide.centerx).midleft,
                duration
            ),
            attr='midleft'
        )
        # slide "quit" in from left to center
        self.quit.rect.driver.run(
            it.chain(
                # delay a bit
                util.lerpsiter(
                    self.quit.rect.copy(left=self.slide.left).midleft,
                    self.quit.rect.copy(left=self.slide.left).midleft,
                    duration / 4
                ),
                util.lerpsiter(
                    self.quit.rect.copy(left=self.slide.left).midleft,
                    self.quit.rect.copy(centerx=self.slide.centerx).midleft,
                    duration
                ),
            ),
            attr='midleft'
        )
        # player intro
        rect = g.player.sprite.rect
        rect.driver.run(
            it.chain(
                util.lerpsiter(
                    rect.copy(midbottom=g.screen.rect.midtop).center,
                    rect.copy(midtop=g.screen.rect.midbottom).center,
                    duration,
                    lerpfunc=util.sinlerp),
                util.lerpsiter(
                    rect.copy(midtop=g.screen.rect.midbottom).center,
                    rect.copy(midbottom=logofinal.midtop).center,
                    duration,
                    lerpfunc=util.sinlerp)
            )
            attr='center'
        )
        self.brain.append(self.intro)

    def intro(self):
        if not g.player.sprite.rect.driver.iterable:
            self.logger.info("exit intro")
            self.brain.pop()

    def outro_init(self):
        self.logger.info('outro_init')
        duration = 1
        # slide player down
        rect = g.player.sprite.rect
        rect.driver.run(
            util.lerpsiter(
                rect.copy().midbottom,
                rect.copy(bottom=g.screen.rect.bottom - PAD).midbottom,
                duration
            ),
            attr='midbottom'
        )
        # slide logo off
        rect = self.logo.rect
        rect.driver.run(
            util.lerpsiter(
                rect.copy().midleft,
                rect.copy(left=self.slide.left).midleft,
                duration
            ),
            attr='midleft'
        )
        # slide "play" off
        rect = self.play.rect
        rect.driver.run(
            util.lerpsiter(
                rect.midleft,
                rect.copy(right=self.slide.right).midleft,
                duration
            ),
            attr='midleft'
        )
        # slide "quit" off
        rect = self.quit.rect
        rect.driver.run(
            it.chain(
                # hold
                util.lerpsiter(rect.midleft, rect.midleft, .25),
                util.lerpsiter(
                    rect.midleft,
                    rect.copy(right=self.slide.right).midleft,
                    duration
                ),
            ),
            attr='midleft'
        )
        self.eventhandlers.disable()
        self.brain.append(self.outro)

    def outro(self):
        """
        Switch to GameState when quit is done animating.
        """
        if not self.quit.rect.driver.iterable:
            self.logger.info("switching to GameState")
            self.brain.pop()
            g.statestack.append(GameState())

    def on_KEYDOWN(self, event):
        self.logger.info('KEYDOWN')
        if event.key == pg.K_ESCAPE:
            pg.event.post(Event(pg.QUIT))
        elif event.key == pg.K_RETURN:
            # transition to gameplay
            self.outro_init()


class GameState(State):
    """
    Playing the space-shooter typing game.
    """
    def __init__(self):
        super().__init__()
        self.enemies = Group()
        g.sprites.add(g.player)

    def enter(self):
        super().enter()
        self.intro_init()
        self.eventhandlers.enable()

    def exit(self):
        super().exit()
        self.logger.info('exiting')
        self.eventhandlers.disable()

    def intro_init(self):
        # XXX: when re-entering this state, it's paused.
        self.logger.info('intro_init: disabling eventhandlers')
        self.eventhandlers.disable()
        self.brain.append(self.intro)

    def intro(self):
        if not g.player.sprite.rect.driver.iterable:
            self.logger.debug('intro: %s', g.player.sprite.rect)
            self.brain.pop()
            self.gameplay_init()

    def gameplay_init(self):
        self.logger.info('gameplay_init: enabling eventhandlers')
        self.logger.debug('gameplay_init: %s', g.player.sprite.rect)
        self.eventhandlers.enable()
        self.brain.append(self.gameplay)

    def gameplay(self):
        """
        Spawn more EnemyGroup groups if there's no Enemy subclass sprites left.
        """
        self.logger.debug('gameplay, %s', g.player.sprite.rect)
        if not any(isinstance(sprite, Enemy) for sprite in g.sprites.sprites()):
            self.do_spawn()

    def outro_init(self):
        self.eventhandlers.disable()
        # fly player off screen, up
        duration = 1
        rect = g.player.sprite.rect
        rect.driver.run(
            it.chain(
                util.lerpsiter(
                    rect.center,
                    rect.copy(midtop=g.screen.rect.midbottom).center,
                    duration / 8,
                    lerpfunc=util.sinlerp),
                util.lerpsiter(
                    rect.copy(midtop=g.screen.rect.midtop).center,
                    rect.copy(midbottom=g.screen.rect.midtop).center,
                    duration,
                    lerpfunc=util.sinlerp)
            ),
            attr='center',
        )
        self.brain.append(self.outro)

    def outro(self):
        """
        Wait for player to fly off.
        """
        if not g.player.sprite.rect.driver.iterable:
            self.brain.pop()
            for enemy in self.enemies.sprites():
                enemy.kill()
            g.statestack.pop()

    def on_KEYDOWN(self, event):
        if event.key == pg.K_ESCAPE:
            # pause
            g.statestack.append(GamePauseState())
        elif event.unicode:
            self.do_typed(event.unicode)

    def shoot_at(self, ship):
        bullet = Bullet(ship)
        bullet.rect.midbottom = g.player.sprite.rect.midtop
        bullet.start = bullet.rect.copy()
        g.sprites.add(bullet)

    def kill_letter(self, word, letter):
        for group in g.sprites.allgroups():
            if (isinstance(group, EnemyGroup) and group.word == word):
                group.word = group.word[1:]
                if getattr(self, 'typing_at', None) is None:
                    g.sprites.add(PolygonTarget(group.ship, 6))
                for sprite in group.sprites():
                    if isinstance(sprite, LetterSprite) and sprite.letter == letter:
                        self.shoot_at(group.ship)
                        # TODO: whatever's being typed at should be above the
                        #       other sprites; and this below isn't working.
                        #       the sprites stop moving and being shot at.
                        #for sprite in group.sprites():
                        #    sprite._layer += 1
                        sprite.kill()
                        break
                return

    def do_typed(self, letter):
        if getattr(self, 'typing_at', None) is None:
            word = g.game.find(letter)
            if word:
                self.kill_letter(word, letter)
                self.typing_at = g.game.hit_word(word)
        else:
            if self.typing_at.startswith(letter):
                self.kill_letter(self.typing_at, letter)
                self.typing_at = g.game.hit_word(self.typing_at)

    def do_spawn(self):
        """
        Spawn new wave of Enemy sprites.
        """
        self.logger.info('do_spawn')
        g.game.spawnmax()
        for word in g.game.active_words:
            size = random.choice(SHIP_CHOICES)
            enemygroup = EnemyGroup(word, size)
            bounding = enemygroup.boundingrect()
            enemygroup.position(bounding.random(g.spawnrect))
            g.sprites.add(enemygroup)
            self.enemies.add(enemygroup)


class GamePauseState(State):

    def __init__(self):
        super().__init__()
        self.resume = LogoSprite("Escape to resume")
        self.quit = LogoSprite("Enter to quit")
        self.quit.rect.midtop = self.resume.rect.move(0, PAD).midbottom
        self.pause_group = Group(self.resume, self.quit)
        self.pause_group.positioned(center=g.screen.rect.center)

    def get_sprites_to_pause(self):
        """
        Return sprites that should be paused on pausing.
        """
        for sprite in g.sprites.sprites():
            if isinstance(sprite, (Enemy, Effect)):
                yield sprite

    def enter(self):
        self.logger.info('enter')
        for sprite in self.get_sprites_to_pause():
            sprite.active = False
        g.sprites.add(self.pause_group)

    def exit(self):
        self.logger.info('exit')
        self.quit.kill()
        self.resume.kill()
        for sprite in self.get_sprites_to_pause():
            sprite.active = True
        g.sprites.remove(self.pause_group)

    def on_KEYDOWN(self, event):
        if event.key == pg.K_ESCAPE:
            # unpause
            g.statestack.pop()
        elif event.key == pg.K_RETURN:
            # quit to main menu
            g.statestack.pop()
            g.statestack[-1].outro_init()


class Sprite(pg.sprite.DirtySprite):

    def __init__(self):
        super().__init__()
        self.dirty = 2
        self.image = Surface((0,0))
        self.rect = self.image.get_rect()
        self.active = True
        self._layer = 0

    def update(self):
        self.rect.update()


class LogoSprite(Sprite):

    def __init__(self, text, scale=1):
        super().__init__()
        image = g.font.render(text, True, Color('white'))
        self.image = pg.transform.scale(image, scaled(image.get_size(), scale))
        self.rect = Rect(self.image.get_rect())


class Effect(Sprite):

    def __init__(self):
        super().__init__()


class Explosion(Effect):

    def __init__(self, position, duration=.5, startradius=None, endradius=None):
        super().__init__()
        self.x, self.y = position

        if startradius is None:
            startradius = 1
        if endradius is None:
            endradius = min(g.screen.rect.size) / 8

        self.radiusiter = util.lerpiter(startradius, endradius, duration)
        self.widthiter = util.lerpiter(0, 0, duration)
        self.alphaiter = util.lerpiter(200, 0, duration)

        rect = self.rect = Rect(0, 0, startradius * 2, startradius * 2)
        rect.center = (self.x, self.y)
        self.image = Surface(self.rect.size)

    def update(self):
        super().update()
        try:
            radius = int(next(self.radiusiter))
            width = int(next(self.widthiter))
            alpha = int(next(self.alphaiter))
        except StopIteration:
            self.kill()
            return

        self.rect.size = (radius * 2, ) * 2
        self.rect.center = (self.x, self.y)
        self.image = image = Surface(self.rect.size)
        color = Color('gold', alpha=alpha)
        draw.circle(image, color, image.get_rect().center, radius, width)


class Target(Effect):

    def __init__(self, target, duration=.5, startradius=None, endradius=None):
        super().__init__()
        self.target = target

        if startradius is None:
            startradius = min(g.screen.rect.size)
        if endradius is None:
            endradius = 1

        self.radiusiter = util.lerpiter(startradius, endradius, duration)
        self.widthiter = util.lerpiter(16, 1, duration)
        self.alphaiter = util.lerpiter(255, 125, duration)

        rect = self.rect = Rect(0, 0, startradius * 2, startradius * 2)
        rect.center = self.target.rect.center
        self.image = Surface(self.rect.size)

    def update(self):
        super().update()
        try:
            radius = int(next(self.radiusiter))
            width = int(next(self.widthiter))
            alpha = int(next(self.alphaiter))
        except StopIteration:
            self.kill()
            return

        self.rect.size = (radius * 2, ) * 2
        self.rect.center = self.target.rect.center
        self.image = image = Surface(self.rect.size)
        color = Color('white', alpha=alpha)
        draw.circle(image, color, image.get_rect().center, radius, width)


class PolygonTarget(Effect):

    def __init__(self, target, sides, duration=.5, startradius=None, endradius=None):
        super().__init__()
        self.target = target
        self.sides = sides
        if startradius is None:
            startradius = min(g.screen.rect.size)
        if endradius is None:
            endradius = 1
        self.radiusiter = util.lerpiter(startradius, endradius, duration)
        self.widthiter = util.lerpiter(8, 1, duration)
        self.alphaiter = util.lerpiter(255, 125, duration)
        self.angles = tuple(util.lerprange(0, tau, 1/self.sides))
        self.rotation = 0
        self.rotation_step = math.radians(2)

    def update(self):
        super().update()
        try:
            radius = int(next(self.radiusiter))
            width = int(next(self.widthiter))
            alpha = int(next(self.alphaiter))
        except StopIteration:
            self.kill()
            return
        points = tuple((radius + math.cos(angle + self.rotation) * radius,
                        radius + math.sin(angle + self.rotation) * radius)
                        for angle in self.angles)
        diameter = radius * 2
        self.image = Surface((diameter, diameter))
        color = Color('gold', alpha=alpha)
        pg.draw.polygon(self.image, color, points, width)

        self.rect = self.image.get_rect()
        self.rect.center = self.target.rect.center

        self.rotation += self.rotation_step


class PlayerSprite(Sprite):

    def __init__(self):
        super().__init__()
        self._layer = 1
        self.image = Surface((32, 64))
        self.image.fill(Color('red'))
        self.rect = self.image.get_rect()


class PlayerGroup(Group):

    def __init__(self):
        super().__init__()
        self.sprite = PlayerSprite()
        self.add(self.sprite)


class Bullet(Sprite):

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.image = Surface((8, 8))
        draw.circle(self.image,
                    Color('white'),
                    self.image.get_rect().center,
                    min(self.image.get_size()) // 2)
        self.rect = self.image.get_rect()
        self.time = 0
        self.duration = .25
        self.start = self.rect.copy()

    def update(self):
        super().update()
        self.time += g.dt / 1000
        if self.time >= self.duration:
            self.target.health -= 1
            if self.target.health == 0:
                self.target.kill()

                explosion = Explosion(self.target.rect.center, endradius=min(g.screen.rect.size)/2)
                for group in self.groups():
                    group.add(explosion)
            else:
                explosion = Explosion(self.target.rect.center)
                for group in self.groups():
                    group.add(explosion)

            self.kill()

        t = self.time / self.duration
        self.rect.x = util.lerp(self.start.x, self.target.rect.centerx, t)
        self.rect.y = util.lerp(self.start.y, self.target.rect.centery, t)


class LetterSprite(Sprite):

    def __init__(self, letter):
        super().__init__()
        self.letter = letter
        self.image = g.font.render(letter, True, Color('white'), Color(0,0,0,25))
        self.rect = Rect(self.image.get_rect())


class LetterGroup(Group):

    def __init__(self, word):
        super().__init__()
        for letter in word:
            self.add(LetterSprite(letter))


class Enemy:
    pass


class EnemyShip(Sprite, Enemy):

    def __init__(self, word, size):
        super().__init__()
        self.word = word
        self.health = len(word)

        self.lettergroup = LetterGroup(word)
        self.image = Surface(size)
        draw.circle(self.image,
                    Color('red'),
                    self.image.get_rect().center,
                    min(self.image.get_size()) // 2)
        self.rect = self.image.get_rect()
        self.x, self.y = self.rect.center

        lettersprites = self.lettergroup.sprites()
        for ls1, ls2 in zip(lettersprites[:-1], lettersprites[1:]):
            ls2.rect.left = ls1.rect.right
        self.lettergroup.positioned(midtop=self.rect.midbottom)

        self.speedmultiplier = 1
        self.x, self.y = self.rect.center

    def update(self):
        super().update()
        dx, dy = deltato(self.rect.center, g.player.sprite.rect.center, self.speedmultiplier)
        self.x += dx
        self.y += dy
        self.rect.center = (self.x, self.y)
        self.lettergroup.positioned(midtop=self.rect.midbottom)


class EnemyGroup(Enemy, Group):

    def __init__(self, word, size):
        super().__init__()
        self.word = word
        self.ship = EnemyShip(word, size)
        self.add(self.ship.lettergroup)
        self.add(self.ship)


class G:
    # setup by Engine
    dt = None
    font = None
    screen = None
    spawnrect = None

    game = Group()
    player = PlayerGroup()
    sprites = Group()
    statestack = StateStack()

g = G()

class Engine:

    def __init__(self, stepper=False):
        self.logger = getlogger(self)
        self.npass, self.nfail = pg.init()
        self.logger.info('npass: %s, nfail: %s', self.npass, self.nfail)

        g.screen = Screen(SCREENSIZE)
        g.font = pg.font.Font(None, FONTSIZE)
        g.spawnrect = g.screen.rect.copy(
                height=g.screen.rect.height * .3,
                midbottom=g.screen.rect.midtop)

        self.stepper = stepper
        self.do_step = not self.stepper

        self.clock = Clock(FRAMERATE)

        self.buffered_events = deque()
        self.running = False

        self.eventhandlers = EventHandlerGroup.from_instance(self)

    def on_KEYDOWN(self, event):
        self.logger.info('on_KEYDOWN: %s', event)
        if (event.type == pg.KEYDOWN
                and event.key == pg.K_TAB
                and (event.mod & pg.KMOD_SHIFT)):
            self.stepper = not self.stepper
            if not self.stepper:
                self.do_step = True
        elif (event.type == pg.KEYDOWN
                and event.key == pg.K_TAB
                and not (event.mod & pg.KMOD_SHIFT)):
            self.do_step = True

    def on_QUIT(self, event):
        self.logger.info('on_QUIT: %s', event)
        self.running = False

    def handle_event(self, event):
        """
        Find and event handler on this class or the current state and call it,
        passing the event.
        """
        self.logger.info('handle_event: %s', event)

        event_name = TYPE2NAME[event.type]
        handler = self.eventhandlers.get(event_name, None)
        if handler and handler.enabled:
            handler(event)

        if g.statestack:
            handler = g.statestack[-1].eventhandlers.get(event_name, None)
            if handler and handler.enabled:
                handler(event)

    def run(self):
        self.running = True
        while self.running:
            self.step()

    def step(self):
        """
        Process a single frame step.
        """
        g.dt = self.clock.tick()

        events = pg.event.get()
        if self.do_step:
            while self.buffered_events:
                events.insert(0, self.buffered_events.popleft())
        else:
            self.buffered_events.extend(events)

        for event in events:
            self.handle_event(event)

        if self.do_step and g.statestack:
            g.statestack[-1].update()
            g.sprites.update()
            g.sprites.clear(g.screen.image, g.screen.background)
            dirty = g.sprites.draw(g.screen.image)
            pg.display.update(dirty)

        if self.stepper:
            self.do_step = False


def bind_and_run(func, args):
    bound = inspect.signature(func).bind(**vars(args))
    return func(*bound.args, **bound.kwargs)

def main():
    """
    ZPype: A clone of ZType, http://zty.pe
    """
    parser = argparse.ArgumentParser(prog='zpype', description=main.__doc__)
    parser.add_argument('--words', type=argparse.FileType(), default='words.txt')
    parser.add_argument('--logging')
    parser.add_argument('--filter', nargs='+', default='',
                        help='Only show logging from this name. %(default)s')
    parser.add_argument('--stepper', action='store_true',
                        help='Start game in step mode. TAB to step, SHIFT+TAB'
                             ' to toggle stepping.')
    args = parser.parse_args()

    words = [line.strip() for line in args.words if len(line.strip()) > 2]
    del args.words

    if args.logging or args.filter:
        logging.basicConfig(level=getattr(logging, args.logging))
    del args.logging

    # XXX: multiple filters not working
    if args.filter:
        logger = logging.getLogger(MODULENAME)
        for name in args.filter:
            logger.addFilter(logging.Filter(name))
    del args.filter

    engine = bind_and_run(Engine, args)
    g.game = Game(words, 4)
    g.statestack.append(MainmenuState())
    engine.run()

if __name__ == '__main__':
    main()
