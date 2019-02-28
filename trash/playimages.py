import argparse
import pygame as pg

def main():
    """
    """
    parser = argparse.ArgumentParser(prog='playimages', description=main.__doc__)
    parser.add_argument('files', nargs='+', type=argparse.FileType('rb'))
    parser.add_argument('--delay', default=100)
    parser.add_argument('--background', type=argparse.FileType('rb'))
    args = parser.parse_args()

    pg.init()
    clock = pg.time.Clock()
    screen = pg.display.set_mode((800,600))
    space = screen.get_rect()
    if args.background:
        background = pg.transform.scale(pg.image.load(args.background), space.size)
    else:
        background = screen.copy()

    font = pg.font.Font(None, 48)
    image = font.render("Loading...", True, pg.Color('white'))
    screen.blit(image, image.get_rect(center=space.center))
    pg.display.flip()

    images = [pg.image.load(file).convert_alpha() for file in args.files]
    i = 0
    delay = args.delay

    running = True
    while running:
        dt = clock.tick(60)
        if delay - dt <= 0:
            delay = (delay - dt) % args.delay
            i = (i + 1) % len(images)
        else:
            delay -= dt
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
                break
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    pg.event.post(pg.event.Event(pg.QUIT))
        screen.blit(background,(0,0))
        image = images[i]
        screen.blit(image, image.get_rect(center=space.center))
        pg.display.flip()

if __name__ == '__main__':
    main()
