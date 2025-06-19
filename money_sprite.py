import pygame


# ---------------------------------------------------------------------------
#  Money sprite
# ---------------------------------------------------------------------------
class MoneySprite(pygame.sprite.Sprite):
    def __init__(self, value: float, image: pygame.Surface, pos):
        super().__init__()
        self.value = round(value, 2)
        self.image = image
        self.rect = self.image.get_rect(topleft=pos)
        self.dragging = False
        self.offset = (0, 0)
        self.in_pay_area = False
        self.highlighted = False
        self.initial_pos = None
