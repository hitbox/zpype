import argparse
import contextlib
import math
import os
import random

with contextlib.redirect_stdout(open(os.devnull, 'w')):
    import pygame as pg

def align(rects, **kwargs):
    """
    Taken pairwise, set the attribute of the second rect to an attribute of the first.

    e.g.: align(iter_of_rects, left='right'),
          to set the `left` attr of each second rect to the `right` attr of
          each first.

    :param rects: sliceable container.
    """
    for r1, r2 in zip(rects[:-1], rects[1:]):
        for k2, k1 in kwargs.items():
            setattr(r2, k2, getattr(r1, k1))

def wrap(rects):
    attrs = ((rect.left, rect.top, rect.right, rect.bottom) for rect in rects)
    lefts, tops, rights, bottoms = zip(*attrs)
    left, top, right, bottom = min(lefts), min(tops), max(rights), max(bottoms)
    return pg.Rect(left, top, right - left, bottom - top)

def randomxy(inside):
    x = random.randint(inside.left, inside.right)
    y = random.randint(inside.top, inside.bottom)
    return (x, y)

def randomresolve(rect, inside, rects):
    while any(rect.colliderect(r) for r in rects):
        rect.topleft = randomxy(inside)

class image:

    @staticmethod
    def strip(surf):
        """
        Strip a surface of whole row/column transparent pixels.
        """
        width, height = surf.get_size()
        # breaking on the index that has any non-alpha pixels leaves us with the
        # index we want...
        for left in range(width):
            if any(surf.get_at((left, y)).a != 0 for y in range(height)):
                break
        for top in range(height):
            if any(surf.get_at((x, top)).a != 0 for x in range(width)):
                break
        # ...but breaking on the index with non-alpha pixels leaves us on the wrong
        # side of the pixel when going backwards. so we break on the index who's
        # next row or col has the non-alpha pixel.
        for right in range(width, 0, -1):
            if any(surf.get_at((right - 1, y)).a != 0 for y in range(height)):
                break
        for bottom in range(height, 0, -1):
            if any(surf.get_at((x, bottom - 1)).a != 0 for x in range(width)):
                break
        return surf.subsurface(pg.Rect(left, top, right-left, bottom-top)).copy()

class Clock:

    def __init__(self, framerate):
        self.framerate = framerate
        self._clock = pg.time.Clock()

    def tick(self):
        return self._clock.tick(self.framerate)


class Screen:

    def __init__(self, size):
        self.image = pg.display.set_mode(size)
        self.background = self.image.copy()
        self.rect = self.image.get_rect()

    def clear(self):
        self.image.blit(self.background, (0, 0))

    def flip(self):
        pg.display.flip()

    def update(self):
        self.flip()


class Engine:

    def __init__(self, clock, screen):
        self.clock = clock
        self.screen = screen

    def run(self, scene):
        scene.begin()
        while not pg.event.peek(pg.QUIT):
            dt = self.clock.tick()
            for event in pg.event.get():
                if event.type in scene.dispatcher:
                    scene.dispatcher[event.type](event)
            scene.update()
            self.screen.clear()
            scene.draw(self.screen.image)
            self.screen.update()


event_method_prefix = 'on_'

def event_method_name(event_type):
    """
    :param event_type: pygame event type
    """
    event_name = pg.event.event_name(event_type).lower()
    return f'{event_method_prefix}{event_name}'

class Dispatcher:

    def __init__(self, parent):
        self.parent = parent

    def __contains__(self, event_type):
        attrname = event_method_name(event_type)
        return attrname in dir(self)

    def __getitem__(self, event_type):
        attrname = event_method_name(event_type)
        return getattr(self, attrname)

    def __setitem__(self, event_type, func):
        setattr(self, event_method_name(event_type), func)


class Font(pg.font.Font):

    def render(self, text, color, antialias=True, background=None):
        images = [
            super(Font, self).render(line, antialias, color, background)
            for line in text.splitlines()]
        rects = [image.get_rect() for image in images]
        align(rects, top='bottom')
        result = pg.Surface(wrap(rects).size, pg.SRCALPHA)
        for image, rect in zip(images, rects):
            result.blit(image, rect)
        return result


class Scene:

    dispatcher_class = Dispatcher

    def __init__(self, engine):
        self.engine = engine
        self.dispatcher = self.dispatcher_class(self)

    def begin(self):
        pass

    def draw(self, image):
        pass

    def update(self):
        pass


class Particle(pg.sprite.Sprite):

    def __init__(self, *groups, size=None, color=None, ttl=None):
        super().__init__(*groups)
        if size is None:
            size = (1, 1)
        self.image = pg.Surface(size, pg.SRCALPHA)
        if color is None:
            color = (200, 200, 200, 125)
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.x = self.y = 0
        self.vx = self.vy = 0
        self.ax = self.ay = 0
        self.t = 0
        if ttl is None:
            ttl = 60 * 3
        self.ttl = ttl

    def update(self, *args):
        self.vx += self.ax
        self.vy += self.ay
        self.x += self.vx
        self.y += self.vy
        self.rect.topleft = (self.x, self.y)
        self.t += 1
        if self.t > self.ttl:
            self.kill()


def sprite2particles(sprite, alphathreshold=0, center=None, accel=None):
    if center is None:
        center = sprite.rect.center
    centerx, centery = center
    if accel is None:
        accel = (.005, .005)
    accelx, accely = accel
    particles = []
    for y in range(sprite.image.get_height()):
        for x in range(sprite.image.get_width()):
            color = sprite.image.get_at((x,y))
            if color.hsva[3] > alphathreshold:
                p = Particle(color=color)
                p.x = sprite.rect.x + x
                p.y = sprite.rect.y + y
                dx = centerx - p.x
                dy = centery - p.y
                distance = math.hypot(dx, dy)
                angle = math.atan2(dy, dx)
                p.ax = math.cos(angle) * -distance * accelx
                p.ay = math.sin(angle) * -distance * accely
                particles.append(p)
    return particles


def tupint(s):
    return tuple(map(int, s.split(',')))

class ArgumentParser(argparse.ArgumentParser):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_argument('--size', default='800,600', type=tupint)
        self.add_argument('--framerate', default=60)
