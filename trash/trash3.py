class Shooter(Scene):

    def begin(self):
        self.dispatcher = ShooterDispatcher(self)
        self.words = [ word.lower() for word in wordsgen()
                       if 3 <= len(word) <= 6
                       and set(word).issubset(string.ascii_letters)]
        self.level = random.sample(self.words, 10)
        self.group = pg.sprite.Group()
        self.ship = Ship()
        self.ship.rect.midbottom = (400, 600)
        self.ship.x = self.ship.rect.centerx
        self.ship.y = self.ship.rect.centery
        self.group.add(self.ship)

        self.overlays = []

        self.total = 0
        self.misses = 0
        self.hits = 0
        self.kills = 0

        sprite1 = Text(lambda: f'misses: {self.misses}')
        self.group.add(sprite1)

        sprite2 = Text(lambda: f'hits: {self.hits}')
        self.group.add(sprite2)

        sprite3 = Text(lambda: f'ratio: {self.hits / self.total if self.total > 0 else "NA":.2}')
        self.group.add(sprite3)

        sprite4 = Text(lambda: f'health: {self.ship.health}/{self.ship.maxhealth}')
        self.group.add(sprite4)

        sprite4.rect.bottomleft = (0, 600)
        sprite3.rect.bottomleft = sprite4.rect.topleft
        sprite2.rect.bottomleft = sprite3.rect.topleft
        sprite1.rect.bottomleft = sprite2.rect.topleft

        def calc():
            return 1 - (
                    (len(self.level)
                        + sum(1 for sprite in self.group if isinstance(sprite, Word)))
                    / 10)

        progress = Progress(calc, pg.Rect(500,550,250,25))
        self.overlays.append(progress)

        self.locked = None

    def attack(self, letter):
        self.total += 1
        if not self.locked:
            def key(sprite):
                dx = sprite.rect.centerx - self.ship.rect.centerx
                dy = sprite.rect.centery - self.ship.rect.centery
                return math.hypot(dx, dy)
            bynearest = sorted(self.group, key=key)
            for sprite in bynearest:
                if isinstance(sprite, Word) and sprite.letters[0] == letter:
                    self.locked = sprite
                    self.overlays.append(Locked(self.locked))
                    break
            else:
                self.misses += 1
        if self.locked:
            if self.locked.letters and self.locked.letters[0] == letter:
                laser = Laser(self.locked)
                laser.rect.midbottom = self.ship.rect.midtop
                laser.x = laser.rect.centerx
                laser.y = laser.rect.centery
                self.group.add(laser)
                self.locked.hit()
                self.hits += 1
                if not self.locked.letters:
                    self.locked.kill()
                    self.kills += 1
                    self.locked = None
            elif self.locked.letters:
                self.misses += 1

    def draw(self, surf):
        self.group.draw(surf)
        for overlay in self.overlays:
            overlay.draw(surf)
        for sprite in self.group:
            pg.draw.rect(surf, (150,10,10), sprite.rect, 1)

    def update(self):
        if self.locked and not self.locked.alive():
            self.locked = None
        nwords = sum(1 for sprite in self.group if isinstance(sprite, Word))
        if nwords < 4:
            if self.level:
                word = self.level.pop()
                sprite = Word(word, self.ship)
                if nwords > 0:
                    while True:
                        x = random.randint(0, 800 - sprite.rect.width)
                        y = random.randint(-sprite.rect.height * 2, -sprite.rect.height)
                        sprite.rect.topleft = (x, y)
                        others = (other for other in self.group if isinstance(other, Word))
                        if not any(other.rect.colliderect(sprite) for other in others):
                            break
                sprite.x = sprite.rect.centerx
                sprite.y = sprite.rect.centery
                self.group.add(sprite)
        remove = set()
        for overlay in self.overlays:
            overlay.update()
            if not overlay.alive():
                remove.add(overlay)
        for overlay in remove:
            self.overlays.remove(overlay)
        self.group.update()
