import argparse
import contextlib
import math
import os
import random
import string
from pathlib import Path

import framework as fw
from framework import pg

def wordsgen(predicate=None):
    with open('/usr/share/dict/words') as f:
        for word in f.readlines():
            yield word.strip()

words = list(word for word in wordsgen()
             if 4 <= len(word) <= 6
             and set(word).issubset(string.ascii_lowercase))
random.shuffle(words)

class Letter(pg.sprite.Sprite):

    def __init__(self, letter, *groups):
        if len(letter) != 1:
            raise RuntimeError('letter must be length 1, got %r' % letter)
        super().__init__(*groups)
        self.letter = letter
        font = pg.font.Font(None, 32)
        self.image = font.render(str(letter), True, (200,200,200))
        self.rect = self.image.get_rect()

    def kill(self):
        particles = fw.sprite2particles(self)
        for group in self.groups():
            group.add(*particles)
        super().kill()


class Word:

    def __init__(self, letters):
        self.original = letters
        self.letters = self.original
        self.sprites = list(map(Letter, self.letters))
        self.y = 0
        self.align()

    def align(self):
        fw.align(self.rects(), left='right', top='top')

    def is_alive(self):
        return bool(self.letters)

    def is_hit(self, letter):
        return self.letters and letter == self.letters[0]

    def rect(self):
        return fw.wrap(self.rects())

    def rects(self):
        return tuple(sprite.rect for sprite in self.sprites)

    def shoot(self, letter):
        if not self.is_hit(letter):
            return
        self.letters = self.letters[1:]
        self.sprites[0].kill()
        self.sprites.pop(0)
        return True

    def update(self, *args):
        if self.sprites:
            self.y += .5
            self.sprites[0].rect.y = self.y
            self.align()


class TypingDispatcher(fw.Dispatcher):

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))
        else:
            self.parent.shoot(event.unicode)


class TypingScene(fw.Scene):

    dispatcher_class = TypingDispatcher

    def begin(self):
        self.sprites = pg.sprite.Group()
        self.draw = self.sprites.draw
        self.words = []
        self.lock = None
        self.nwords = 3

    def letters(self):
        return (sprite for sprite in self.sprites if isinstance(sprite, Letter))

    def shoot(self, letter):
        if self.lock and not self.lock.is_alive():
            self.lock = None
        if self.lock:
            self.lock.shoot(letter)
        else:
            for word in self.words:
                if word.shoot(letter):
                    self.lock = word
                    break

    def spawn(self):
        while True:
            letters = random.choice(words)
            taken = any(word.letters == letters for word in self.words)
            if not taken:
                break
        newword = Word(letters)
        rect = newword.rect()
        spawn = pg.Rect(100, -4 * rect.height, 800-100-rect.width, rect.height)
        rect.topleft = fw.randomxy(spawn)
        fw.randomresolve(rect, spawn, [w.rect() for w in self.words])
        newword.sprites[0].rect.topleft = rect.topleft
        newword.y = newword.sprites[0].rect.y
        newword.align()
        self.sprites.add(newword.sprites)
        self.words.append(newword)

    def update(self, *args):
        self.sprites.update(*args)
        if len(self.words) < self.nwords:
            self.spawn()
        for word in self.words:
            word.update(*args)
        self.words = [word for word in self.words if word.is_alive()]


def main(argv=None):
    """
    """
    parser = fw.ArgumentParser(prog=Path(__file__).stem, description=main.__doc__)
    args = parser.parse_args(argv)

    pg.init()
    clock = fw.Clock(args.framerate)
    screen = fw.Screen(args.size)
    engine = fw.Engine(clock, screen)
    scene = FontScene(engine)
    engine.run(scene)

if __name__ == '__main__':
    main()
