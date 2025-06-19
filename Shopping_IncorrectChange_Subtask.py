import os
import random
import pygame
from base_task import BaseTask
from enum import Enum

# Directory containing currency images
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


class ChangeMode(Enum):
    FIFTY_FIFTY = 1
    ALWAYS_RIGHT = 2
    ALWAYS_WRONG = 3


# Map currency values to image filenames in assets/
CURRENCY_IMAGE_MAP = {
    5.00: "5dollar.png",
    1.00: "1dollar.png",
    0.25: "quarter.png",
    0.10: "dime.png",
    0.05: "nickel.png",
    0.01: "penny.png",
}

# Desired sprite sizes
BILL_SIZE = (260, 130)
COIN_SIZE = (60, 60)
SPACING_X = 20
SPACING_Y = 20


class MoneySprite(pygame.sprite.Sprite):
    def __init__(self, value: float, pos):
        super().__init__()
        self.value = round(value, 2)
        filename = CURRENCY_IMAGE_MAP.get(self.value)
        if not filename:
            raise ValueError(f"No image mapping for currency value {self.value}")
        image_path = os.path.join(ASSETS_DIR, filename)
        try:
            img = pygame.image.load(image_path).convert_alpha()
        except Exception:
            raise FileNotFoundError(f"Could not load currency image: {image_path}")
        size = BILL_SIZE if self.value >= 1.00 else COIN_SIZE
        img = pygame.transform.smoothscale(img, size)
        self.image = img
        self.rect = self.image.get_rect(topleft=pos)
        self.initial_pos = pos
        self.dragging = False
        self.offset = (0, 0)


class IncorrectChange(BaseTask):
    def __init__(self, screen, change_mode):
        super().__init__(screen, subtask_id="incorrect_change")
        self.price = 1.25
        self.payment_amount = 5.00
        self.change_mode = change_mode
        self.phase = 1
        self.dragging = False
        self.dragged_sprite = None
        self.show_change_guess = False
        self.change_guess_active = False
        self.correct = False

        w, h = screen.get_size()
        self.payment_area = pygame.Rect((w - 400) // 2, (h - 500) // 2, 400, 200)
        self.change_box = pygame.Rect((w - 150) // 2, 20, 600, 550)
        self.yes_btn = pygame.Rect(50, h - 100, 150, 50)
        self.no_btn = pygame.Rect(300, h - 100, 150, 50)
        self.surrender_btn = pygame.Rect(150, 500, 200, 50)
        self.highlight_yes = False  # Flag for highlighting buttons
        self.highlight_no = False

        # When user needs to enter their guess
        self.collect_guess = False
        self.user_guess = ""
        # Position button and textbox
        self.guess_box = pygame.Rect(50, 200, 200, 50)
        self.submit_btn = pygame.Rect(260, 200, 100, 40)

        self.sprites = pygame.sprite.Group()
        self.change_sprites = pygame.sprite.Group()
        self.message = ""  # General directions for the user
        self.change_guess = ""  # Used when the provided changed is wrong and the user needs to calculate correct change
        self.supportive_message = ""  # Used for independence scoring

        shown_amount = sum(sprite.value for sprite in self.change_sprites)
        correct_amount = round(self.payment_amount - self.price, 2)
        self.diff = abs(shown_amount - correct_amount)   # Difference between the shown change and the target change

        # Fonts
        self.font = pygame.font.SysFont(None, 32)
        self.large_font = pygame.font.SysFont(None, 48)

        # Scoring
        self.errors = 0
        self.independence_score = 0
        self.inactive_seconds = 0.0
        self.elapsed = 0.0

        self._init_phase1()

    def _init_phase1(self):
        self.sprites.empty()
        self.change_sprites.empty()
        self.phase = 1
        bx = (self.screen.get_width() - BILL_SIZE[0]) // 2
        by = self.screen.get_height() - BILL_SIZE[1] - 20
        self.sprites.add(MoneySprite(5.00, (bx, by)))

    def _init_phase2(self):
        # Determine correctness
        if self.change_mode == ChangeMode.ALWAYS_RIGHT:
            self.correct = True
        elif self.change_mode == ChangeMode.ALWAYS_WRONG:
            self.correct = False
        else:
            self.correct = random.random() < 0.5
        correct_due = round(self.payment_amount - self.price, 2)
        amt = correct_due if self.correct else round(correct_due + (0.20 if random.random() < 0.5 else -0.20), 2)

        # Split into bills and coins
        bills = []
        coins = []
        for denom in [5.00, 1.00]:
            while amt >= denom - 1e-6:
                bills.append(denom)
                amt = round(amt - denom, 2)
        for denom in [0.25, 0.10, 0.05, 0.01]:
            while amt >= denom - 1e-6:
                coins.append(denom)
                amt = round(amt - denom, 2)

        # Render bills on left side
        self.change_sprites.empty()
        start_x_b = self.change_box.left + SPACING_X
        start_y = self.change_box.top + self.large_font.get_height() + SPACING_Y
        max_b_y = self.change_box.bottom - SPACING_Y
        col_x = start_x_b
        col_y = start_y
        for value in bills:
            if col_y + BILL_SIZE[1] > max_b_y:
                col_y = start_y
                col_x += BILL_SIZE[0] + SPACING_X
            self.change_sprites.add(MoneySprite(value, (col_x, col_y)))
            col_y += BILL_SIZE[1] + SPACING_Y

        # Render coins on right side
        start_x_c = self.change_box.right - SPACING_X - COIN_SIZE[0]
        col_x = start_x_c
        col_y = start_y
        max_c_y = self.change_box.bottom - SPACING_Y
        for value in coins:
            if col_y + COIN_SIZE[1] > max_c_y:
                col_y = start_y
                col_x -= COIN_SIZE[0] + SPACING_X
            self.change_sprites.add(MoneySprite(value, (col_x, col_y)))
            col_y += COIN_SIZE[1] + SPACING_Y

        self.phase = 2
        self.message = ""

    def _custom_event_handler(self, event):
        # Phase 1 Event Handling
        if self.phase == 1:
            if event.type == pygame.MOUSEBUTTONDOWN:

                for spr in self.sprites:
                    if spr.rect.collidepoint(event.pos):
                        self.dragging = True
                        self.dragged_sprite = spr
                        mx, my = event.pos
                        spr.offset = (mx - spr.rect.x, my - spr.rect.y)
                        break

            elif event.type == pygame.MOUSEMOTION and self.dragging:
                mx, my = event.pos
                ox, oy = self.dragged_sprite.offset
                self.dragged_sprite.rect.topleft = (mx - ox, my - oy)
            elif event.type == pygame.MOUSEBUTTONUP and self.dragging:
                if self.payment_area.collidepoint(event.pos):
                    self._init_phase2()
                else:
                    self.dragged_sprite.rect.topleft = self.dragged_sprite.initial_pos
                self.dragging = False
                self.dragged_sprite = None

        # replace your guess‐typing block with this
        if self.collect_guess:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    self.user_guess = self.user_guess[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._finish_guess()
                else:
                    # allow digits and one dot
                    ch = event.unicode
                    if ch.isdigit() or (ch == "." and "." not in self.user_guess):
                        self.user_guess += ch

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # submit button
                if self.submit_btn.collidepoint(event.pos):
                    self._finish_guess()
                # still allow “Give Up” even while typing
                elif self.surrender_btn.collidepoint(event.pos):
                    # exactly the same surrender logic you have in phase 2:
                    self._complete(False, self.diff)
            return


        # Phase 2 Event Handling
        elif self.phase == 2 and event.type == pygame.MOUSEBUTTONDOWN:
            self.inactive_seconds = 0.0  # Reset inactivity

            total = sum(sp.value for sp in self.change_sprites)
            correct_sum = round(self.payment_amount - self.price, 2)
            if self.yes_btn.collidepoint(event.pos):
                if total == correct_sum:
                    self.message = "Yes — Thanks!"
                    self._complete(True)
                else:
                    self.message = "No - Actually it was wrong"
                    self.errors += 1
            elif self.no_btn.collidepoint(event.pos):
                if total != correct_sum:
                    # start collecting their guess
                    self.collect_guess = True
                    self.message = "Yes - Enter the correct change and submit"
                else:
                    self.message = "No — Actually it was right."
                    self.errors += 1
                    self._complete(False, self.diff)
            elif self.surrender_btn.collidepoint(event.pos):
                # Check for change accuracy difference
                if not self.correct:
                    # Minor miss
                    if self.diff < 1.5:
                        self.independence_score = 7
                    # Major miss
                    else:
                        self.independence_score = 8
                else:
                    self.independence_score = 9

                # Terminate the program
                self._complete(False, self.diff)

    def _render(self):
        self.screen.fill((255, 255, 255))

        if self.phase == 1:
            pygame.draw.rect(self.screen, (200, 200, 240), self.payment_area)
            pa_label = self.font.render("Payment Area", True, (0, 0, 100))
            self.screen.blit(pa_label, (self.payment_area.centerx - pa_label.get_width() // 2,
                                        self.payment_area.y + 10))
            inst = "Drag the $5 bill into the payment area"
            self.screen.blit(self.font.render(inst, True, (50, 50, 50)), (370, 20))
            self.sprites.draw(self.screen)
        else:

            status = f"You paid ${self.payment_amount:.2f} for an item that costed ${self.price:.2f}"
            self.screen.blit(self.font.render(status, True, (0, 0, 0)), (20, 20))

            if self.collect_guess:
                # draw the input box
                color = (255, 255, 255)
                pygame.draw.rect(self.screen, color, self.guess_box)
                pygame.draw.rect(self.screen, (0, 0, 0), self.guess_box, 2)
                # render the current input
                txt_surf = self.font.render(self.user_guess, True, (0, 0, 0))
                self.screen.blit(txt_surf, (self.guess_box.x + 5, self.guess_box.y + 5))

                # draw submit button
                pygame.draw.rect(self.screen, (100, 200, 100), self.submit_btn)
                lbl = self.font.render("Submit", True, (0, 0, 0))
                self.screen.blit(lbl, (self.submit_btn.centerx - lbl.get_width() // 2,
                                       self.submit_btn.centery - lbl.get_height() // 2))

            # draw "Give Up" button
            pygame.draw.rect(self.screen, (200, 100, 100), self.surrender_btn)
            lbl = self.font.render("Give Up", True, (0, 0, 0))
            self.screen.blit(lbl, (self.surrender_btn.centerx - lbl.get_width() // 2,
                                   self.surrender_btn.centery - lbl.get_height() // 2))

            pygame.draw.rect(self.screen, (240, 240, 200), self.change_box)
            lbl = self.large_font.render("Change Received", True, (80, 80, 0))
            self.screen.blit(lbl, ((self.change_box.centerx - lbl.get_width() // 2),
                                   self.change_box.top + 10))
            self.change_sprites.draw(self.screen)
            q = self.font.render("Is this the correct change?", True, (0, 0, 0))
            qy = self.change_box.bottom + SPACING_Y
            self.screen.blit(q, (100, 600))
            pygame.draw.rect(self.screen, (0, 200, 0), self.yes_btn)
            self.screen.blit(self.font.render("Yes", True, (0, 0, 0)),
                             (self.yes_btn.x + 50, self.yes_btn.y + 12))  # Draw text on Yes button
            pygame.draw.rect(self.screen, (200, 0, 0), self.no_btn)
            self.screen.blit(self.font.render("No", True, (0, 0, 0)),
                             (self.no_btn.x + 60, self.no_btn.y + 12))  # Draw text on No button

            if self.highlight_no:
                pygame.draw.rect(screen, (0, 0, 255), self.no_btn, 5)
            if self.highlight_yes:
                pygame.draw.rect(screen, (0, 0, 255), self.yes_btn, 5)

            # Render text box if necessary
            if self.show_change_guess:
                color = (255, 255, 255) if self.change_guess_active else (200, 200, 200)
                pygame.draw.rect(self.screen, color, self.guess_box)
                pygame.draw.rect(self.screen, (0, 0, 0), self.guess_box, 2)  # border

                # render the text
                txt_surf = self.font.render(self.change_guess, True, (0, 0, 0))
                screen.blit(txt_surf, (self.guess_box.x + 5, self.guess_box.y + 5))

        if self.message:
            self.screen.blit(self.font.render(self.message, True, (100, 0, 0)), (20, 100))
        if self.supportive_message:
            self.screen.blit(self.font.render(self.supportive_message, True, (200, 10, 100)), (500, 650))
        pygame.display.flip()

    # ---- HELPER METHODS ----
    def _finish_guess(self):
        s = self.user_guess.strip().lstrip('$')
        try:
            entered = round(float(s), 2)
        except ValueError:
            self.message = "Please enter a valid number like 1.25"
            return

        due = round(self.payment_amount - self.price, 2)
        # compare to within a half‐cent
        if abs(entered - due) < 0.005:
            self.result_data["user_guess"] = entered
            self.running = False
        else:
            self.message = f"You entered ${entered:.2f}. Try again or give up."

    def _update(self):
        dt_ms = self.clock.tick(60)
        self.inactive_seconds += dt_ms / 1000
        self.elapsed += dt_ms / 1000

        if self.phase == 2:
            # Independence Calculations
            if self.inactive_seconds > 5 and self.independence_score == 0:
                # Show an encouraging message
                self.supportive_message = "You Got This!"
                self.inactive_seconds = 0
                self.independence_score = 1

            if self.inactive_seconds > 3 and self.independence_score == 1:
                # Show a verbal directive cue
                self.supportive_message = "Click YES if the change is correct and NO otherwise"
                self.inactive_seconds = 0
                self.independence_score = 2

            if self.inactive_seconds > 3 and self.independence_score == 2:
                # Highlight the buttons
                self.highlight_yes = True
                self.highlight_no = True
                self.inactive_seconds = 0
                self.independence_score = 3

            if self.inactive_seconds > 3 and self.independence_score == 3:
                # Highlight the correct button
                self.highlight_yes = False
                self.highlight_no = False
                if self.correct:
                    self.highlight_yes = True
                else:
                    self.highlight_no = True
                self.inactive_seconds = 0
                self.independence_score = 4

            if self.inactive_seconds > 3 and self.independence_score == 4:
                self.inactive_seconds = 0
                self.independence_score = 5

            if self.inactive_seconds > 3 and self.independence_score == 5:
                self.independence_score = 6

    def _complete(self, success=False, error=None):
        # Calculate quality and process scores
        quality = 3
        process = 0
        if success:
            if self.errors > 4:
                process = 0
            elif self.errors > 3:
                process = 1
            elif self.errors > 2:
                process = 2

        if self.diff < .1:
            quality = 2
        elif self.diff < .5:
            quality = 1
        else:
            quality = 0

        self.result_data.update({
            "subtask_id": "Incorrect Change",
            "duration_sec": self.elapsed,
            "errors": self.errors,
            "independence_score": self.independence_score,
            "quality_score": quality,
            "process_score": process,
            "success": success,
        })
        self.running = False


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1124, 768))
    task = IncorrectChange(screen, ChangeMode.ALWAYS_WRONG)
    task.run()
    print(task.get_results())
    pygame.quit()
