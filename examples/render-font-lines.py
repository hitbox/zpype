import argparse
import textwrap
from pathlib import Path
import framework as fw
from framework import pg

class FontScene(fw.Scene):

    def begin(self):
        self.dispatcher[pg.KEYDOWN] = self.on_keydown
        self.group = pg.sprite.Group()
        sprite = pg.sprite.Sprite()
        font = fw.Font(None, 32)
        lorem = textwrap.dedent('''\
        Lorem ipsum dolor sit amet, consectetur adipiscing elit.
        Phasellus quis enim nec odio sodales hendrerit eu sit amet tellus.
        Vestibulum ut hendrerit sem.
        Aenean facilisis, sapien luctus fringilla viverra, turpis turpis interdum ante, id finibus est purus et risus.
        Class aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos himenaeos.
        Nunc maximus elementum urna eu lacinia.
        Nam tempus commodo leo sed vehicula.
        Sed porta mauris id nibh dapibus, nec accumsan ligula molestie.
        Proin sed eros ut ipsum dignissim lacinia.
        Praesent vehicula, ex eu egestas lobortis, tortor metus convallis turpis, sit amet iaculis orci lectus sit amet erat.
        Proin euismod est quis mauris malesuada, ut accumsan massa mattis.
        In vitae mi elit. Nunc congue augue non pellentesque tempor.''')
        sprite.image = font.render(lorem, (200,200,200))
        sprite.rect = sprite.image.get_rect()
        self.group.add(sprite)
        self.draw = self.group.draw

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
    scene = FontScene(engine)
    engine.run(scene)

if __name__ == '__main__':
    main()
