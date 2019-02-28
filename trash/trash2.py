from collections import UserDict, UserList

import argparse
import pygame as pg

pg.init()

class Clock:

    def __init__(self, framerate):
        self.framerate = framerate
        self.dt = None
        self._clock = pg.time.Clock()

    def update(self):
        self.dt = self._clock.tick(self.framerate)


class Screen:

    def __init__(self, size):
        self.size = size
        self.image = pg.display.set_mode(size)
        self.background = self.image.copy()
        self.rect = self.image.get_rect()

    def clear(self):
        self.image.blit(self.background, (0,0))

    def update(self):
        pg.display.flip()


class Surface(pg.Surface):

    def __init__(self, size, flags=pg.SRCALPHA):
        super().__init__(size, flags)


class Sprite(pg.sprite.Sprite):

    def __init__(self,
            size,
            color,
            rotation = 0,
            scale = 1,
            *groups,
            **position
        ):
        super().__init__(*groups)
        self._image = Surface(size)
        self._image.fill(color)
        self.rect = self._image.get_rect(**position)
        self.rotation = rotation
        self.scale = scale
        self._image_cache = {}

    @property
    def image(self):
        key = (self.scale, self.rotation)
        if key not in self._image_cache:
            size = tuple(map(lambda x: int(x * self.scale), self._image.get_size()))
            if size[0] > 0 and size[1] > 0:
                image = pg.transform.scale(self._image, size)
            else:
                image = self._image.copy()
            self._image_cache[key] = pg.transform.rotate(image, self.rotation)
        return self._image_cache[key]


class Entity:

    def __init__(self, sprite, controller):
        self.sprite = sprite
        self.controller = controller


class EventHandler:

    def __init__(self, func, enabled=True):
        self.func = func
        self.enabled = enabled

    def handle(self, event):
        if self.enabled:
            self.func(event)


class EventDispatcher(UserDict):

    def __setitem__(self, event_type, func):
        assert callable(func), '`func` must be callable'
        super().__setitem__(event_type, EventHandler(func))

    def handle(self, event):
        if event.type in self:
            self[event.type].handle(event)


class ControlStack(UserList):

    def update(self):
        return self[-1]()


class Controller:

    def __init__(self):
        self.controlstack = ControlStack()

    def update(self):
        self.controlstack.update()


class SearchController(Controller):

    def __init__(self, sprite, inside):
        self.sprite = sprite
        self.inside = inside
        self.controlstack = ControlStack([self.moving])

    def moving(self):
        pass


class State:

    def __init__(self):
        self.eventdispatcher = EventDispatcher()
        self.controlstack = ControlStack([self.update])

    def draw(self, surface):
        pass

    def enter(self):
        """
        """

    def update(self):
        """
        """


class TestState(State):

    def enter(self):
        self.eventdispatcher[pg.KEYDOWN] = self.on_keydown
        self.sprite = Sprite((128,128), (255,0,0), centery=300)
        pg.draw.circle(
            self.sprite._image,
            (200,200,200),
            self.sprite._image.get_rect().move(32,0).center,
            32
        )
        self.group = pg.sprite.Group(self.sprite)
        self.controlstack.append(self.move_sprite_right)

    def move_sprite_right(self):
        if self.sprite.rect.right >= 800:
            self.sprite.rect.right = 800
            self.controlstack.pop()
            return
        self.sprite.rect.x += 10
        self.sprite.rotation += 8

    def draw(self, surface):
        self.group.draw(surface)

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:
            raise StopEngine
        else:
            print(event)


class StopEngine(Exception):
    """
    """


class Engine:

    def __init__(self, clock, screen, state):
        self.clock = clock
        self.screen = screen
        self.state = state

    def run(self):
        self.state.enter()
        try:
            while True:
                self.step()
        except StopEngine:
            pass

    def step(self):
        for event in pg.event.get():
            # TODO: switch state
            if event.type == pg.QUIT:
                raise StopEngine
            elif event.type in self.state.eventdispatcher:
                self.state.eventdispatcher.handle(event)
        self.state.controlstack.update()
        self.screen.clear()
        self.state.draw(self.screen.image)
        self.screen.update()
        self.clock.update()


def tupleint(arg):
    return tuple(map(int, arg.split(',')))

def main(args=None):
    """
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--screensize', type=tupleint, default='800,600', help='%(default)s')
    parser.add_argument('--framerate', type=int, default=60, help='%(default)s')
    args = parser.parse_args()

    clock = Clock(args.framerate)
    screen = Screen(args.screensize)
    state = TestState()
    engine = Engine(clock, screen, state)
    engine.run()

if __name__ == '__main__':
    main()
