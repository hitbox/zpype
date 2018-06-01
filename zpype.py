import argparse
import inspect
import math
import random
from collections import OrderedDict, defaultdict, deque
from itertools import chain
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

def rollfor(chance):
    """
    Return bool indicating one-in-chance roll.
    """
    return random.randint(1, chance) == 1

def scaled(iter, x):
    return tuple(v * x for v in iter)

def lerp(a, b, t):
    return (1 - t) * a + t * b

def sinlerp(a, b, t):
    f = math.sin(t * math.pi / 2)
    return (1 - f) * a + f * b

def coslerp(a, b, t):
    f = (1 - math.cos(t * math.pi / 2))
    return a * (1 - f) + b * f

def lerpiter(a, b, duration):
    time = 0
    while time <= duration:
        yield lerp(a, b, time / duration)
        time += dt / 1000
    if time > duration:
        yield lerp(a, b, 1)

class draw:

    @staticmethod
    def circle(surface, color, position, radius, width=0):
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


class State(Group):

    def on_enter(self):
        self._saved_sprites = getattr(self, '_saved_sprites', self.sprites())
        for sprite in self._saved_sprites:
            self.add(sprite)

    def on_exit(self):
        for sprite in self.sprites():
            sprite.kill()
            self._saved_sprites.append(sprite)


class IntroState(State):

    def __init__(self):
        super().__init__()
        self.brain = Machine()
        self.logo = LogoSprite("ZPype", 6)
        self.logo.rect.center = screen.rect.center

        self.play = LogoSprite("Enter to play", 2)
        self.quit = LogoSprite("Escape to quit", 2)

        self.play.rect.midtop = self.logo.rect.move(0, PAD).midbottom
        self.quit.rect.midtop = self.play.rect.move(0, PAD).midbottom

        self.introiter = None
        self.add(self.brain, self.logo, playersprite, self.play, self.quit)

    def on_enter(self):
        super().on_enter()

        # all relative to playersprite.top
        self.introiter = chain(
            lerpiter(
                screen.rect.top - playersprite.rect.height,
                self.quit.rect.bottom + PAD,
                0.5),
            lerpiter(
                self.quit.rect.bottom + PAD,
                self.logo.rect.top + PAD - playersprite.rect.height,
                1)
        )
        self.brain.stack.append(self.brain_move_player_in)

    def brain_move_player_in(self):
        try:
            playersprite.rect.top = next(self.introiter)
        except StopIteration:
            self.brain.stack.pop()

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))
        elif event.key == pg.K_RETURN:
            pg.event.post(pg.event.Event(SWITCH, state=GameState))


class GameState(State):

    def __init__(self):
        super().__init__()
        self.brain = Machine()
        self.introiter = None
        self.add(self.brain, playersprite)

    def on_enter(self):
        super().on_enter()
        for sprite in self.sprites():
            if isinstance(sprite, Enemy):
                sprite.kill()
        self.introiter = lerpiter(playersprite.rect.bottom, screen.rect.bottom - 10, .5)
        self.brain.stack.append(self.brain_intro)

    def brain_intro(self):
        try:
            playersprite.rect.bottom = next(self.introiter)
        except StopIteration:
            self.brain.stack.pop()

    def brain_outro(self):
        try:
            playersprite.rect.top = next(self.outroiter)
        except StopIteration:
            self.brain.stack.pop()
            pg.event.post(pg.event.Event(SWITCH, state=IntroState))

    def brain_game_pause(self):
        pass

    def get_sprites_to_pause(self):
        # original thought some needed excluding
        for sprite in self.sprites():
            yield sprite

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:

            if self.brain.current == self.brain_game_pause:
                self.outroiter = lerpiter(playersprite.rect.top, screen.rect.bottom, .1)
                self.brain.stack.append(self.brain_outro)

            else:
                for sprite in self.get_sprites_to_pause():
                    sprite.active = False
                self.resume = LogoSprite("Enter to resume")
                self.quit = LogoSprite("Escape to quit")
                self.quit.rect.midtop = self.resume.rect.move(0, PAD).midbottom
                group = Group(self.resume, self.quit)
                group.positioned(center=screen.rect.center)

                self.add(group)
                self.brain.stack.append(self.brain_game_pause)

        elif event.key == pg.K_RETURN:
            if self.brain.current == self.brain_game_pause:
                self.brain.stack.pop()
                self.quit.kill()
                self.resume.kill()
                for sprite in self.get_sprites_to_pause():
                    sprite.active = True

        elif event.unicode:
            self.do_typed(event.unicode)

    def shoot_at(self, ship):
        bullet = Bullet(ship)
        bullet.rect.midbottom = playersprite.rect.midtop
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
            size = random.choice(SHIP_CHOICES)
            enemygroup = EnemyGroup(word, size)

            bounding = enemygroup.boundingrect()
            enemygroup.position(bounding.random(spawnrect))

            self.add(enemygroup)

    def update_spawn(self):
        """
        Spawn more EnemyGroup groups if there's no Enemy subclass sprites left.
        """
        if not any(isinstance(sprite, Enemy) for sprite in self.sprites()):
            self.do_spawn()

    def update(self):
        super().update()
        self.update_spawn()


class Sprite(pg.sprite.Sprite):

    def __init__(self):
        super().__init__()
        self.image = Surface((0,0))
        self.rect = self.image.get_rect()
        self.active = True


class Machine(Sprite):
    # Sprite subclass because Group classes only call their sprites' update methods.

    def __init__(self, initial=None):
        super().__init__()
        self.stack = []
        if initial is not None:
            self.stack.append(initial)

    @property
    def current(self):
        return None if not self.stack else self.stack[-1]

    def update(self):
        if self.current:
            self.current()


class LogoSprite(Sprite):

    def __init__(self, text, scale=1):
        super().__init__()
        image = font.render(text, True, Color('white'))
        self.image = pg.transform.scale(image, scaled(image.get_size(), scale))
        self.rect = self.image.get_rect()


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
            endradius = min(screen.rect.size) / 8

        self.radiusiter = lerpiter(startradius, endradius, duration)
        self.widthiter = lerpiter(0, 0, duration)
        self.alphaiter = lerpiter(200, 0, duration)

        rect = self.rect = Rect(0, 0, startradius * 2, startradius * 2)
        rect.center = (self.x, self.y)
        self.image = Surface(self.rect.size)

    def update(self):
        if not self.active:
            return
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

    def __init__(self, target, duration=.25, startradius=None, endradius=None):
        super().__init__()
        self.target = target

        if startradius is None:
            startradius = min(screen.rect.size)
        if endradius is None:
            endradius = 1

        self.radiusiter = lerpiter(startradius, endradius, duration)
        self.widthiter = lerpiter(16, 1, duration)
        self.alphaiter = lerpiter(255, 125, duration)

        rect = self.rect = Rect(0, 0, startradius * 2, startradius * 2)
        rect.center = self.target.rect.center
        self.image = Surface(self.rect.size)

    def update(self):
        if not self.active:
            return
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
        self.image = Surface((32, 64))
        self.image.fill(Color('red'))
        self.rect = self.image.get_rect()


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
        if not self.active:
            return
        self.time += dt / 1000
        if self.time >= self.duration:
            self.target.health -= 1
            if self.target.health == 0:
                self.target.kill()

                explosion = Explosion( self.target.rect.center, endradius=min(screen.rect.size)/2)
                for group in self.groups():
                    group.add(explosion)
            else:
                explosion = Explosion(self.target.rect.center)
                for group in self.groups():
                    group.add(explosion)

            self.kill()

        t = self.time / self.duration
        self.rect.x = lerp(self.start.x, self.target.rect.centerx, t)
        self.rect.y = lerp(self.start.y, self.target.rect.centery, t)


class LetterSprite(Sprite):

    def __init__(self, letter):
        super().__init__()
        self.letter = letter
        self.image = font.render(letter, True, Color('white'), Color(0,0,0,25))
        self.rect = self.image.get_rect()


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
        self.rect = Rect(self.image.get_rect())
        self.x, self.y = self.rect.center

        lettersprites = self.lettergroup.sprites()
        for ls1, ls2 in zip(lettersprites[:-1], lettersprites[1:]):
            ls2.rect.left = ls1.rect.right
        self.lettergroup.positioned(midtop=self.rect.midbottom)

        self.speedmultiplier = 0.5

    def update(self):
        if not self.active:
            return
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

    def __init__(self, word, size):
        super().__init__()
        self.word = word
        self.ship = EnemyShip(word, size)
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
