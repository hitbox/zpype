import argparse
import functools
import string
import textwrap
from pathlib import Path
import framework as fw
from framework import pg

def scaler(mult):
    def wrapped(surf):
        width, height = map(lambda x: x * mult, surf.get_size())
        return pg.transform.scale(surf, (width, height))
    return wrapped

class SheetFont:

    def __init__(self, letter_images):
        self.letter_images = letter_images
        self.lettermap = {letter: image for letter, image
                in zip(string.ascii_uppercase, self.letter_images)}

    def render(self, text, xpad=1, ypad=1):
        images = []
        rects = []
        previous = None
        for line in text.splitlines():
            for char in line:
                image = self.lettermap[char]
                if previous is None:
                    right = 0
                else:
                    right = previous.right + xpad
                rect = image.get_rect(left=right)
                images.append(image)
                rects.append(rect)
                previous = rect.copy()
            previous.left = 0
            previous.top += previous.height + ypad
        result = pg.Surface(fw.wrap(rects).size, pg.SRCALPHA)
        for image, rect in zip(images, rects):
            result.blit(image, rect)
        return result


class MonospaceScene(fw.Scene):

    def begin(self):
        self.dispatcher[pg.KEYDOWN] = self.on_keydown
        self.group = pg.sprite.Group()
        self.sprite = pg.sprite.Sprite(self.group)

        sheet = pg.image.load('assets/simplefont.png')
        sheet = sheet.subsurface(pg.Rect(0, 10, 260, 10))

        images = (sheet.subsurface(pg.Rect(xo,0,10,10)) for xo in range(0, 260, 10))
        images = list(map(scaler(10), map(fw.image.strip, images)))

        font = SheetFont(images)
        self.image = font.render('HELLOWORLDX', xpad=10, ypad=10)

    def draw(self, surf):
        surf.blit(self.image, (0,0))

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))


def main(argv=None):
    """
    """
    parser = fw.ArgumentParser(prog=Path(__file__).stem, description=main.__doc__)
    args = parser.parse_args(argv)

    pg.init()
    clock = fw.Clock(args.framerate)
    screen = fw.Screen(args.size)
    engine = fw.Engine(clock, screen)
    scene = MonospaceScene(engine)
    engine.run(scene)

if __name__ == '__main__':
    main()
