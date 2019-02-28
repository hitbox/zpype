import argparse
import pygame as pg

def lerp(a, b, t):
    return (1 - t) * a + t * b

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timestep', default=0.1, type=float)
    args = parser.parse_args()

    pg.init()

    screen = pg.display.set_mode((240,200))
    space = screen.get_rect()
    font = pg.font.Font(None, 40)

    source = pg.image.load("assets/png/explosion.png").convert_alpha()
    finalalphas = pg.surfarray.array_alpha(source)

    # NOTE: this was an effort to pre-compute lerp-ing the per-pixel alphas of
    #       an image.

    i = 1
    t = 0
    while t <= 1:
        pg.event.pump()
        image = font.render(f'{t / 1 * 100:.0f}%', True, pg.Color('white'))
        screen.fill(pg.Color('black'))
        screen.blit(image, image.get_rect(center=space.center))
        pg.display.flip()

        image = source.copy()
        array = pg.surfarray.pixels_alpha(image)
        array[:] = [ [ lerp(0, finalalphas[y][x], t)
                       for x, alpha in enumerate(row) ]
                     for y, row in enumerate(array) ]
        del array
        pg.image.save(image, f"assets/png/explosion{i}.png")
        t += args.timestep
        i += 1


if __name__ == '__main__':
    main()
