import pygame as pg

w = h = 8
inside = pg.Rect(0,-h,1,h*5)
moving = pg.Rect(0,7,w,h)

for _ in range(15):
    print(moving)
    moving.y = inside.top + ((moving.y + 3) % inside.height)
