import argparse
import inspect
import math
import random
from collections import OrderedDict, defaultdict
from pathlib import Path

import pygame as pg

SCREENSIZE = (500, 1000)
FRAMERATE = 60
FONTSIZE = 32
PAD = 10

SWITCH = pg.USEREVENT

BIG_SHIP = (64, 32)
SMALL_SHIP = (32, 32)

SHIP_CHOICES = list()
SHIP_CHOICES.extend((SMALL_SHIP, ) * 10)
SHIP_CHOICES.extend((BIG_SHIP, ) * 1)

global current_state, dt, font, game, playersprite, screen, spawnrect
current_state = dt = font = game = playersprite = screen = spawnrect = None


def lerp(a, b, t):
    return (1 - t) * a + t * b

def sinlerp(a, b, t):
    f = math.sin(t * math.pi / 2)
    return (1 - f) * a + f * b

def coslerp(a, b, t):
    f = (1 - math.cos(t * math.pi / 2))
    return a * (1 - f) + b * f

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


class Rect(pg.Rect):

    def copy(self, *args, **kwargs):
        rect = super().copy()
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


class Surface(pg.Surface):

    def __init__(self, size, flags=pg.SRCALPHA):
        super().__init__(size, flags)


class Group(pg.sprite.OrderedUpdates):

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


class GameGroup(Group):

    def get_playersprite(self):
        for sprite in self.sprites():
            if isinstance(sprite, PlayerSprite):
                return sprite

    def fire_bullet(self, lettersprite):
        lettersprite.toremove = True
        lettersprite.lockedon = True

        bullet = Bullet(lettersprite)
        bullet.rect.midtop = self.get_playersprite().rect.midtop
        bullet.start = bullet.rect.copy()
        bullet.x = bullet.rect.x
        bullet.y = bullet.rect.y

        self.add(bullet)

    def kill_letter(self, word, letter):
        for group in self.spritesgroups():
            if (isinstance(group, EnemyGroup) and group.word == word):
                group.word = group.word[1:]
                for sprite in group.sprites():
                    if isinstance(sprite, LetterSprite) and sprite.letter == letter:
                        sprite.kill()
                        break
                if all(not isinstance(sprite, LetterSprite) for sprite in group.sprites()):
                    for sprite in group.sprites():
                        sprite.kill()
                return

    def do_typed(self, letter):
        if getattr(self, 'typing_at', None) is None:
            word = game.find(letter)
            if word:
                self.kill_letter(word, letter)
                self.typing_at = game.hit_word(word)
        else:
            if self.typing_at.startswith(letter):
                self.kill_letter(self.typing_at, letter)
                self.typing_at = game.hit_word(self.typing_at)

    def do_spawn(self):
        game.spawnmax()
        for word in game.active_words:
            enemygroup = EnemyGroup(word)

            bounding = enemygroup.boundingrect()
            enemygroup.position(bounding.random(spawnrect))

            self.add(enemygroup)

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))
        elif event.unicode:
            self.do_typed(event.unicode)

    def update(self):
        super().update()
        for sprite in self.sprites():
            if isinstance(sprite, LetterSprite):
                break
        else:
            self.do_spawn()


class Sprite(pg.sprite.Sprite):

    def __init__(self):
        super().__init__()


class PlayerSprite(Sprite):

    def __init__(self):
        super().__init__()
        self.image = Surface((32, 64))
        self.image.fill(pg.Color('red'))
        self.rect = self.image.get_rect()


class Bullet(Sprite):

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.image = Surface((8, 8))
        pg.draw.circle(self.image,
                       pg.Color('gold'),
                       self.image.get_rect().center,
                       min(self.image.get_size()))
        self.rect = self.image.get_rect()
        self.time = 0
        self.duration = 0.5
        self.start = self.rect.copy()

    def update(self):
        self.time += (dt / 1000)
        if self.time >= self.duration:
            self.kill()
            self.target.kill()
        t = self.time / self.duration
        self.rect.x = coslerp(self.start.x, self.target.rect.centerx, t)
        self.rect.y = coslerp(self.start.y, self.target.rect.centery, t)


class LetterSprite(Sprite):

    def __init__(self, letter):
        super().__init__()
        self.letter = letter
        self.image = font.render(letter, True, pg.Color('white'), pg.Color(0,0,0,25))
        self.rect = self.image.get_rect()


class LetterGroup(Group):

    def __init__(self, word):
        super().__init__()
        for letter in word:
            self.add(LetterSprite(letter))


class Enemy:
    pass


class LittleEnemyShip(Sprite, Enemy):

    def __init__(self, word):
        super().__init__()
        self.word = word

        self.lettergroup = LetterGroup(word)
        self.image = Surface((16,16))
        pg.draw.circle(self.image, pg.Color('red'), self.image.get_rect().center,
                       min(self.image.get_size()) // 2)
        self.rect = Rect(self.image.get_rect())
        self.x, self.y = self.rect.center

        lettersprites = self.lettergroup.sprites()
        for ls1, ls2 in zip(lettersprites[:-1], lettersprites[1:]):
            ls2.rect.left = ls1.rect.right
        self.lettergroup.positioned(midtop=self.rect.midbottom)

        self.speedmultiplier = 0.5

    def update(self):
        dx = playersprite.rect.centerx - self.rect.centerx
        dy = playersprite.rect.centery - self.rect.centery
        length = math.sqrt(dx * dx + dy * dy)
        dx /= length
        dy /= length
        self.x += dx
        self.y += dy
        self.rect.center = (self.x, self.y)
        self.lettergroup.positioned(midtop=self.rect.midbottom)


class EnemyGroup(Enemy, Group):

    def __init__(self, word):
        super().__init__()
        self.word = word
        self.ship = LittleEnemyShip(word)
        self.add(self.ship.lettergroup)
        self.add(self.ship)


class Engine:

    def __init__(self, state, stepper=False):
        self.npass, self.nfail = pg.init()

        global font, game, playersprite, screen, spawnrect
        screen = Screen(SCREENSIZE)
        font = pg.font.Font(None, FONTSIZE)
        spawnrect = screen.rect.copy(height=screen.rect.height * .3,
                                     midbottom=screen.rect.midtop)

        playersprite = PlayerSprite()
        playersprite.rect.midbottom = screen.rect.move(0, -16).midbottom

        self.stepper = stepper
        self.do_step = not self.stepper

        self.clock = Clock(FRAMERATE)

        self.buffered_events = deque()
        self.running = False

        self.state_instances = {}
        pg.event.post(pg.event.Event(SWITCH, state=state))

    def run(self):
        self.running = True
        while self.running:
            self.step()

    def get_event_handler(self, obj, event):
        name = "on_" + pg.event.event_name(event.type).lower()
        return getattr(obj, name, None)

    def on_quit(self, event):
        self.running = False

    def on_userevent(self, event):
        global current_state
        if hasattr(event, 'state'):
            self.on_switch(event)

    def on_switch(self, event):
        global current_state
        if current_state is not None:
            current_state.on_exit()
            current_state.clear(screen.image, screen.background)
            dirty = current_state.draw(screen.image)
            pg.display.update(dirty)

        state = event.state
        if callable(event.state):
            state = event.state()

        class_  = type(state)
        if class_ in self.state_instances:
            current_state = self.state_instances[class_]
        else:
            current_state = state
            self.state_instances[class_] = state

        current_state.on_enter()

    def on_keydown(self, event):
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

    def handle_event(self, event):
        for obj in [self, current_state]:
            method = self.get_event_handler(obj, event)
            if method is not None:
                method(event)

    def step(self):
        global dt
        dt = self.clock.tick()

        events = pg.event.get()
        if self.do_step:
            while self.buffered_events:
                events.insert(0, self.buffered_events.popleft())
        else:
            self.buffered_events.extend(events)

        for event in events:
            self.handle_event(event)

        if self.do_step and current_state is not None:
            current_state.update()
            current_state.clear(screen.image, screen.background)
            dirty = current_state.draw(screen.image)
            pg.display.update(dirty)

        if self.stepper:
            self.do_step = False

    def no_stepper_step(self):
        global dt
        dt = self.clock.tick()

        for event in pg.event.get():
            self.handle_event(event)

        if current_state is not None:
            current_state.update()
            current_state.clear(screen.image, screen.background)
            dirty = current_state.draw(screen.image)
            pg.display.update(dirty)


def bind_and_run(func, args):
    bound = inspect.signature(func).bind(**vars(args))
    return func(*bound.args, **bound.kwargs)

def main():
    """
    ZPype: A clone of ZType, http://zty.pe
    """
    parser = argparse.ArgumentParser(prog='zpype', description=main.__doc__)
    parser.add_argument('--words', type=argparse.FileType(), default='words.txt')
    parser.add_argument('--stepper', action='store_true',
            help='Start game in step mode. TAB to step, SHIFT+TAB to toggle'
                 ' stepping.')
    args = parser.parse_args()

    words = [line.strip() for line in args.words if len(line.strip()) > 2]
    del args.words

    global game
    game = Game(words, 4)
    args.state = IntroState
    engine = bind_and_run(Engine, args)
    engine.run()

if __name__ == '__main__':
    main()
