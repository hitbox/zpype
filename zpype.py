import argparse
import inspect
import math
import operator
import random
import string
from collections import UserList, UserString, namedtuple
from functools import partial
from operator import methodcaller
from pathlib import Path

import pygame as pg

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


def instanceis(class_or_tuple, obj):
    return isinstance(obj, class_or_tuple)

def one(iterable, predicate):
    """
    Assert only one result.
    """
    results = []
    for item in iterable:
        if predicate(item):
            results.append(item)
    assert len(results) == 1
    return results[0]

def lerp(a, b, t):
    return (1 - t) * a + t * b

def lerps(itera, iterb, t):
    """
    Handle `lerp`ing iterables together.
    """
    # no idea what to name this function
    return tuple(lerp(a, b, t) for a, b, in zip(itera, iterb))

class Global:
    game = None

    screen = None
    clock = None
    group = None
    states = None

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
        self.rect = self.image.get_rect()
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
    pass

def bluelaser():
    path = Path("bluelaser.png")
    image = pg.image.load(str(path))
    return image

def renderbackground(size):
    starspath = Path("./assets/png/starsbackground.png")
    assert starspath.exists()
    tile = pg.image.load(str(starspath))
    twidth, theight = tile.get_size()

    width, height = size
    background = Surface(size)

    for y in range(0, height, theight):
        for x in range(0, width, twidth):
            background.blit(tile, (x, y))

    return background

class Group(pg.sprite.Group):

    def boundingrect(self, **attrs):
        rects = [sprite.rect for sprite in self.sprites()]
        lefts, tops, rights, bottoms = zip(*
                (rect.topleft + rect.bottomright for rect in rects))
        left = min(lefts)
        top = min(tops)
        bounding = Rect(left, top, max(rights) - left, max(bottoms) - top)
        for name, value in attrs.items():
            setattr(bounding, name, value)
        return bounding

    def moveasone(self, rect):
        br = self.boundingrect()
        ox, oy = rect.x - br.x, rect.y - br.y
        for sprite in self.sprites():
            sprite.rect.move_ip(ox, oy)


class Sprite(pg.sprite.Sprite):
    pass


class Laser(Sprite):

    def __init__(self, target, *groups):
        super().__init__(*groups)
        self.target = target
        self._image = self.image = pg.image.load(str(Path('assets/png/bluelaser.png')))
        self.rect = self.image.get_rect()

    def update(self):
        self.rect.center = lerps(self.rect.center, self.target.rect.center, .3)

        dx, dy = (self.target.rect.centerx - self.rect.centerx,
                  self.target.rect.centery - self.rect.centery)
        angle = math.degrees(math.atan2(-dy, dx))
        self.image = pg.transform.rotate(self._image, angle)

        if self.rect.colliderect(self.target.rect):
            self.kill()
            self.target.kill()


class Player(Sprite):

    def __init__(self, *groups):
        super().__init__(*groups)
        x = min(g.screen.rect.size)
        self.image = Surface((x/16, x/8))
        self.image.fill(Color('brown'))
        self.rect = self.image.get_rect()


class Enemy(Sprite):
    pass


class EnemyShip(Enemy):

    def __init__(self, *groups):
        super().__init__(*groups)
        x = min(g.screen.rect.size)
        self.image = Surface((x/16, x/16))
        self.image.fill(Color('purple'))
        self.rect = self.image.get_rect()

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

    def __init__(self, ourship, letter, *groups):
        super().__init__(*groups)
        self.ourship = ourship
        self.letter = letter
        font = Font(None, int(min(g.screen.rect.size)/16))
        self.image = font.render(self.letter, True, Color('white'))
        self.rect = self.image.get_rect()
        self.offset = None

    def update(self, *args):
        if self.offset is None:
            self.offset = (self.rect.x - self.ourship.rect.x,
                           self.rect.y - self.ourship.rect.y)

        ox, oy = self.offset
        self.rect.topleft = (self.ourship.rect.x + ox,
                             self.ourship.rect.y + oy)


class LetterGroup(Group):

    def __init__(self, ourship, letters, *sprites):
        super().__init__(*sprites)
        self.ourship = ourship
        self.letters = letters
        self.lettersprites = []
        x = 0
        for letter in self.letters:
            sprite = LetterSprite(self.ourship, letter)
            sprite.rect.x = x
            x += sprite.rect.width
            self.add(sprite)
            self.lettersprites.append(sprite)


class BackgroundSprite(Sprite):

    def __init__(self, lockto, *groups):
        super().__init__(*groups)
        self.lockto = lockto
        self.offset = None

    def update(self, *args):
        if self.offset is None:
            self.offset = (self.lockto.rect.x - self.rect.x,
                           self.lockto.rect.y - self.rect.y)
        self.rect.topleft = (self.lockto.rect.x - self.offset[0],
                             self.lockto.rect.y - self.offset[1])


class EnemyGroup(Group):

    def __init__(self, word, *sprites):
        super().__init__(*sprites)
        self.word = word
        self.ship = EnemyShip()
        self.lettergroup = LetterGroup(self.ship, list(self.word), self)

        pad = g.padding//4
        bounding = self.lettergroup.boundingrect()

        self.shade = BackgroundSprite(self.ship)
        self.shade.image = Surface(bounding.inflate(pad, pad).size)
        self.shade.image.fill(Color('black', alpha=200))
        self.shade.rect = self.shade.image.get_rect()
        self.shade.rect.midtop = self.ship.rect.move(0, pad).midbottom

        bounding.center = self.shade.rect.center

        self.lettergroup.moveasone(bounding)

        # NOTE: lettergroup needs to update first, to catch the intended,
        #       initial, offset from the ship.
        self.add(self.shade, self.lettergroup, self.ship)


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


class State:

    def __init__(self):
        self.methodstack = list()

        self.eventhandlers = {}
        for name in dir(self):
            attr = getattr(self, name)
            if inspect.ismethod(attr) and name.startswith('on_'):
                self.eventhandlers[name] = EventHandler(attr)

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self):
        if self.methodstack:
            self.methodstack[-1]()


class Engine:

    def __init__(self, screensize, framerate=60, background=None):
        self.npass, self.nfail = pg.init()

        g.screen = Screen(screensize, background=background)
        g.clock = Clock(framerate)
        g.group = Group()
        g.states = StateStack()
        g.padding = min(g.screen.rect.size) / 12

        self.running = False

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
                event_name = "on_" + pg.event.event_name(event.type)
                handler = g.states[-1].eventhandlers.get(event_name)
                if handler is not None and handler.enabled:
                    handler(event)
        g.states[-1].update()
        g.group.update()
        g.group.clear(g.screen.image, g.screen.background)
        dirty = g.group.draw(g.screen.image) or g.screen.rect
        pg.display.update(dirty)


class SimpleSprite(Sprite):

    def __init__(self, *groups):
        super().__init__(*groups)
        self.image = Surface((64, 64))
        self.image.fill(Color('red'))
        self.rect = self.image.get_rect()


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
    return current_player() or Player()

class GameplayState(State):

    def enter(self):
        player = current_player_or_new()
        player.rect.midbottom = g.screen.rect.midtop
        g.player = player
        g.group.add(player)

        self.t = 0
        self.enemygroups = []

        self.methodstack.append(self.playing)
        self.methodstack.append(self.spawn)
        self.eventhandlers['on_KeyDown'].enabled = False
        self.methodstack.append(self.intro)

    def playing(self):
        for enemygroup in self.enemygroups:
            if not any(isinstance(sprite, LetterSprite) for sprite in enemygroup.sprites()):
                for sprite in enemygroup.sprites():
                    sprite.kill()

    def intro(self):
        if self.t <= 1:
            g.player.rect.midbottom = lerps(
                    g.screen.rect.midtop,
                    g.screen.rect.midbottom,
                    self.t)
            self.t += .025
        else:
            self.eventhandlers['on_KeyDown'].enabled = True
            self.methodstack.pop()

    def spawn(self):
        spawned_words = g.game.spawn(4)
        g.game.current.extend(spawned_words)

        spawnrect = g.screen.rect.copy()
        spawnrect.height /= 4
        spawnrect.midbottom = g.screen.rect.midtop

        for word in spawned_words:
            enemygroup = EnemyGroup(word)

            # randomly position the group
            while True:
                position = randomrect(enemygroup.boundingrect(), spawnrect)
                # generate until not colliding
                if not any(position.colliderect(sprite.rect) for sprite in g.group.sprites()):
                    enemygroup.moveasone(position)
                    break

            self.enemygroups.append(enemygroup)
            g.group.add(enemygroup)

        self.methodstack.pop()

    def has_enemies(self):
        # TODO: left off here, there are still enemies after all the letter
        #       sprites have been `kill`ed. so it's never respawning.
        #       also move words.txt to assets dir.
        return any(isinstance(sprite, Enemy) for sprite in g.group.sprites())

    def is_playing(self):
        """
        """
        return self.methodstack[-1] == self.playing

    def shoot(self, letter):
        word = g.game.shoot(letter)
        if word is not None:
            target = None
            for sprite in g.group.sprites():
                if isinstance(sprite, LetterSprite):
                    if sprite.letter == letter:
                        for group in sprite.groups():
                            if isinstance(group, EnemyGroup):
                                if group.word.initial == word.initial:
                                    target = sprite
                                    break
                if target is not None:
                    break

            laser = Laser(target)
            laser.rect.midbottom = g.player.rect.midtop
            g.group.add(laser)

            if not self.has_enemies():
                self.methodstack.append(self.spawn)

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
    with open("words.txt") as words_file:
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
    background = renderbackground(size)
    g.game = TypingGame(getwords())
    engine = Engine(size, background=background)

    stateclass = GameplayState
    engine.run(stateclass())

if __name__ == '__main__':
    main()
