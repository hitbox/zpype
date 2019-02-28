import argparse
import pygame as pg

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
    pass


class Sprite(pg.sprite.Sprite):
    pass


class Scene:
    pass


class Engine:

    def __init__(self, screensize, scenes, framerate=60):
        self.screen = Screen(screensize)
        self.clock = Clock(framerate)
        self.scenes = scenes
        self.running = False
        self.scenestack = []

    def run(self, scene):
        self.scenestack.append(self.scenes[scene])
        while self.running:
            self.step()

    def step(self):
        dt = self.clock.tick()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
                return
            else:
                pass # to scene


def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    engine = Engine(
        (500, 1000),
        dict(
            mainmenu = Scene(),
        )
    )
    engine.run('mainmenu')

if __name__ == '__main__':
    main()
