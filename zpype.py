import argparse
import inspect
import itertools as it
import logging
import math
import random
from collections import OrderedDict, UserDict, UserList, defaultdict, deque
from pathlib import Path

import pygame as pg

MODULENAME = Path(__file__).stem

SCREENSIZE = (500, 1000)
FRAMERATE = 60
FONTSIZE = 32
PAD = 10

TYPE2NAME = {eventtype: pg.event.event_name(eventtype).upper()
              for eventtype in range(pg.NOEVENT, pg.NUMEVENTS)
              if pg.event.event_name(eventtype) not in ('Unknown',)}
SWITCH = pg.USEREVENT
TYPE2NAME[SWITCH] = 'SWITCH'
EVENT_METHOD_PREFIX = "on_"

BIG_SHIP = (64, 32)
SMALL_SHIP = (32, 32)

SHIP_CHOICES = list()
SHIP_CHOICES.extend((SMALL_SHIP, ) * 10)
SHIP_CHOICES.extend((BIG_SHIP, ) * 1)

class G:
    current_state = None
    dt = None
    font = None
    game = None
    player = None
    screen = None
    spawnrect = None


g = G()

def loggername(inst):
    return '.'.join([MODULENAME, inst.__class__.__name__])

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
    dx /= length
    dy /= length
    return (dx * speed, dy * speed)

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
        x = random.randint(inside.left, inside.right - self.width)
        y = random.randint(inside.top, inside.bottom - self.height)
        return self.copy(topleft=(x,y))

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
                try:
                    sprite.x = sprite.rect.centerx
                    sprite.y = sprite.rect.centery
                except AttributeError:
                    pass

    def positioned(self, *args, **kwargs):
        rect = self.boundingrect()
        if rect:
            self.position(rect.copy(*args, **kwargs))

    def spritesgroups(self):
        found = set()
        groups = []
        for sprite in self.sprites():
            for group in sprite.groups():
                if group not in found:
                    found.add(group)
                    groups.append(group)
        return groups

    def update(self, *args):
        for sprite in self.sprites():
            if sprite.active:
                sprite.update(*args)


class Brain(UserList):
    """
    Stack-based finite state machine.
    """
    def __init__(self, body, initial=None):
        super().__init__()
        self.body = body
        if initial:
            self.append(initial)

    def push(self, func):
        self.append(func)

    @property
    def current(self):
        return None if not self else self[-1]

    def update(self):
        if self.current:
            self.current()


class EventHandler:

    def __init__(self, name, method, enabled=True):
        self.name = name
        self.method = method
        self.enabled = enabled

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def toggle(self):
        self.enabled = not self.enabled


class EventHandlerGroup(UserDict):

    def disable(self, event_name):
        for handler in self.values():
            handler.disable()

    def enable(self, event_name):
        for handler in self.values():
            handler.enable()

    def toggle(self, event_name):
        for handler in self.values():
            handler.toggle()

    @classmethod
    def from_instance(cls, inst):
        return cls({name: EventHandler(name, get_event_method(inst, type))
                    for type, name in TYPE2NAME.items()})


class State(Group):

    brain_class = Brain

    def __init__(self, *sprites, brain_class=None):
        super().__init__(*sprites)
        if brain_class is None:
            brain_class = self.brain_class
        self.brain = brain_class(self)
        self.logger = logging.getLogger(loggername(self))

        self.eventhandlers = EventHandlerGroup.from_instance(self)

    def enter(self):
        self.logger.info('enter')
        self._saved_sprites = getattr(self, '_saved_sprites', self.sprites())
        for sprite in self._saved_sprites:
            self.add(sprite)

    def exit(self):
        self.logger.info('exit')
        self._saved_sprites = []
        for sprite in self.sprites():
            self.remove(sprite)
            self._saved_sprites.append(sprite)

    def _on(self, event):
        """
        Return the method to hanle `event`.
        """
        self.logger.info('_on: %s', event)
        handler = self.eventhandlers[TYPE2NAME[event.type]]
        if handler.enabled:
            return handler.method(event)

    def update(self, *args):
        super().update(*args)
        self.brain.update()


class IntroState(State):
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

        self.introiter = None
        self.add(g.player, self.logo, self.play, self.quit)

    def enter(self):
        super().enter()
        self.begin_intro()

    def begin_intro(self):
        # slide menu items on from left
        inside = (g.screen.rect
                   # width * 2
                   .inflate(g.screen.rect.width*2,0)
                   # right side on center
                   .copy(right=g.screen.rect.centerx))
        # slide "play" in from left to center
        self.play.rect.driver.run(
            util.lerpsiter(
                self.play.rect.copy(centerx=inside.left).midleft,
                self.play.rect.copy(centerx=inside.right).midleft,
                1
            ),
            attr='midleft'
        )
        # slide "quit" in from left to center
        self.quit.rect.driver.run(
            it.chain(
                # delay a bit
                util.lerpsiter(
                    self.quit.rect.copy(centerx=inside.left).midleft,
                    self.quit.rect.copy(centerx=inside.left).midleft,
                    .25
                ),
                util.lerpsiter(
                    self.quit.rect.copy(centerx=inside.left).midleft,
                    self.quit.rect.copy(centerx=inside.right).midleft,
                    1
                ),
            ),
            attr='midleft'
        )

        # player intro
        self.introiter = it.chain(
            zip(it.repeat(g.screen.rect.centerx),
                util.lerpiter(g.screen.rect.top - g.player.sprite.rect.height,
                         self.quit.rect.bottom + PAD,
                         0.5)),
            zip(it.repeat(g.screen.rect.centerx),
                util.lerpiter(self.quit.rect.bottom + PAD,
                         self.logo.rect.top + PAD - g.player.sprite.rect.height,
                         1)))

        g.player.sprite.rect.driver.run(
            it.chain(
                util.lerpsiter(
                    g.player.sprite.rect.copy(midbottom=g.screen.rect.midtop).center,
                    g.player.sprite.rect.copy(midtop=g.screen.rect.midbottom).center,
                    1,
                    lerpfunc=util.sinlerp),
                util.lerpsiter(
                    g.player.sprite.rect.copy(midtop=g.screen.rect.midbottom).center,
                    g.player.sprite.rect.copy(midbottom=self.logo.rect.midtop).center,
                    1,
                    lerpfunc=util.sinlerp)
            ),
            attr='center',
        )

        self.brain.push(self.intro)

    def intro(self):
        if not g.player.sprite.rect.driver.iterable:
            self.logger.info("exit intro")
            self.brain.pop()

    def on_KEYDOWN(self, event):
        self.logger.info('KEYDOWN')
        if event.key == pg.K_ESCAPE:
            pg.event.post(Event(pg.QUIT))
        elif event.key == pg.K_RETURN:
            pg.event.post(Event(SWITCH, state=GameState))
        # TODO: remove below
        elif event.key == pg.K_r:
            self.begin_intro()


class GameState(State):
    """
    Playing the space-shooter typing game.
    """
    def __init__(self):
        super().__init__()
        self.introiter = None
        self.add(g.player, self.brain)

    def enter(self):
        super().enter()
        self.logger.info(self.sprites())
        self.begin_intro()

    def begin_intro(self):
        rect = g.player.sprite.rect
        rect.driver.run(
            util.lerpsiter(
                rect.midbottom,
                rect.copy(bottom=g.screen.rect.bottom - PAD).midbottom,
                1
            ),
            attr='midbottom'
        )
        self.logger.info('disabling keydown')
        self.eventhandlers['KEYDOWN'].disable()
        self.brain.push(self.intro)

    def intro(self):
        if not g.player.sprite.rect.driver.iterable:
            self.logger.info('enabling keydown')
            self.eventhandlers['KEYDOWN'].enable()
            self.brain.pop()

    def begin_outro(self):
        self.eventhandlers['KEYDOWN'].disable()
        keepx = it.repeat(g.player.sprite.rect.centerx)
        up = g.player.sprite.rect.top - g.player.sprite.rect.height * 2
        self.outroiter = it.chain(
            zip(keepx, util.lerpiter(g.player.sprite.rect.top, up, .3)),
            zip(keepx, util.lerpiter(up, g.screen.rect.bottom, .3)))
        self.brain.push(self.outro)

    def outro(self):
        try:
            g.player.sprite.rect.midtop = next(self.outroiter)
        except StopIteration:
            self.eventhandlers['KEYDOWN'].enable()
            self.brain.pop()
            pg.event.post(Event(SWITCH, state=IntroState))

    def begin_pause(self):
        pass

    def pause(self):
        pass

    def get_sprites_to_pause(self):
        """
        Return sprites that should be paused on pausing.
        """
        for sprite in self.sprites():
            if isinstance(sprite, (Enemy, Effect)):
                yield sprite

    def do_exit(self):
        self.logger.info('exiting')
        self.begin_outro()
        self.logger.info(self.brain.current)

    def do_pause(self):
        self.logger.info('pausing')
        for sprite in self.get_sprites_to_pause():
            sprite.active = False
        self.resume = LogoSprite("Escape to resume")
        self.quit = LogoSprite("Enter to quit")
        self.quit.rect.midtop = self.resume.rect.move(0, PAD).midbottom
        group = Group(self.resume, self.quit)
        group.positioned(center=g.screen.rect.center)
        self.add(group)
        self.brain.push(self.pause)

    def do_resume(self):
        self.logger.info('resuming')
        self.brain.pop()
        self.quit.kill()
        self.resume.kill()
        for sprite in self.get_sprites_to_pause():
            sprite.active = True

    def on_KEYDOWN(self, event):
        if event.key == pg.K_ESCAPE:
            if self.brain.current == self.pause:
                self.do_resume()
            else:
                self.do_pause()
        elif event.key == pg.K_RETURN:
            if self.brain.current == self.pause:
                self.do_exit()
        elif event.unicode:
            self.do_typed(event.unicode)

    def shoot_at(self, ship):
        bullet = Bullet(ship)
        bullet.rect.midbottom = g.player.sprite.rect.midtop
        bullet.start = bullet.rect.copy()
        self.add(bullet)

    def kill_letter(self, word, letter):
        for group in self.spritesgroups():
            if (isinstance(group, EnemyGroup) and group.word == word):
                group.word = group.word[1:]
                if getattr(self, 'typing_at', None) is None:
                    self.add(Target(group.ship))
                for sprite in group.sprites():
                    if isinstance(sprite, LetterSprite) and sprite.letter == letter:
                        self.shoot_at(group.ship)
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
        if self.brain.current == self.intro:
            return
        g.game.spawnmax()
        for word in g.game.active_words:
            size = random.choice(SHIP_CHOICES)
            enemygroup = EnemyGroup(word, size)

            bounding = enemygroup.boundingrect()
            enemygroup.position(bounding.random(g.spawnrect))

            self.add(enemygroup)

    def update(self):
        """
        Spawn more EnemyGroup groups if there's no Enemy subclass sprites left.
        """
        super().update()
        if not any(isinstance(sprite, Enemy) for sprite in self.sprites()):
            self.do_spawn()


class Sprite(pg.sprite.DirtySprite):

    def __init__(self):
        super().__init__()
        self.dirty = 2
        self.image = Surface((0,0))
        self.rect = self.image.get_rect()
        self.active = True

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

                explosion = Explosion( self.target.rect.center, endradius=min(g.screen.rect.size)/2)
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

        self.speedmultiplier = 1.25
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


class Engine:

    def __init__(self, state, stepper=False):
        self.logger = logging.getLogger(loggername(self))
        self.npass, self.nfail = pg.init()
        self.logger.info('npass: %s, nfail: %s', self.npass, self.nfail)

        g.screen = Screen(SCREENSIZE)
        g.font = pg.font.Font(None, FONTSIZE)
        g.spawnrect = g.screen.rect.copy(
                height=g.screen.rect.height * .3,
                midbottom=g.screen.rect.midtop)

        g.player = PlayerGroup()

        self.stepper = stepper
        self.do_step = not self.stepper

        self.clock = Clock(FRAMERATE)

        self.buffered_events = deque()
        self.running = False

        self.state_instances = {}
        pg.event.post(Event(SWITCH, state=state))

    def run(self):
        self.running = True
        while self.running:
            self.step()

    def _on(self, event):
        return get_event_method(self, event.type)

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

    def on_SWITCH(self, event):
        self.logger.info('on_SWITCH: %s', event)
        if g.current_state is not None:
            g.current_state.exit()
            g.current_state.clear(g.screen.image, g.screen.background)
            dirty = g.current_state.draw(g.screen.image)
            pg.display.update(dirty)

        state = event.state
        if callable(event.state):
            state = event.state()

        class_  = type(state)
        if class_ in self.state_instances:
            g.current_state = self.state_instances[class_]
        else:
            g.current_state = state
            self.state_instances[class_] = state

        g.current_state.enter()

    def handle_event(self, event):
        for obj in [self, g.current_state]:
            method = get_event_method(obj, event.type)
            self.logger.info('handle_event: %s, %s', event, method)
            if method is not None and obj._on(event):
                method(event)

    def step(self):
        g.dt = self.clock.tick()

        events = pg.event.get()
        if self.do_step:
            while self.buffered_events:
                events.insert(0, self.buffered_events.popleft())
        else:
            self.buffered_events.extend(events)

        for event in events:
            self.handle_event(event)

        if self.do_step and g.current_state is not None:
            g.current_state.update()
            g.current_state.clear(g.screen.image, g.screen.background)
            dirty = g.current_state.draw(g.screen.image)
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
    parser.add_argument('--logging', action='store_true')
    parser.add_argument('--filter', default='', help='Only show logging from this name. %(default)s')
    parser.add_argument('--stepper', action='store_true',
            help='Start game in step mode. TAB to step, SHIFT+TAB to toggle'
                 ' stepping.')
    args = parser.parse_args()

    words = [line.strip() for line in args.words if len(line.strip()) > 2]
    del args.words

    if args.logging:
        logging.basicConfig(level=logging.INFO)
    del args.logging

    if args.filter:
        # TODO: this isn't working to filter out loggers.
        logging.getLogger(MODULENAME).addFilter(args.filter)
    del args.filter

    g.game = Game(words, 4)
    args.state = IntroState
    engine = bind_and_run(Engine, args)
    engine.run()

if __name__ == '__main__':
    main()
