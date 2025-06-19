import os, random, pygame
from base_task import BaseTask
from money_sprite import MoneySprite

# ---------------------------------------------------------------------------
#  Constants & assets
# ---------------------------------------------------------------------------
WHITE, BLACK, GREY = (255, 255, 255), (0, 0, 0), (230, 230, 230)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

WALLET_COUNTS = {
    5.00: 1,  # one $5 bill
    1.00: 5,  # five $1 bills
    0.25: 4,  # four quarters
    0.10: 10,  # ten dimes
    0.05: 10,  # ten nickels
    0.01: 10,  # ten pennies
}
DENOM_NAME = {
    0.01: "penny",
    0.10: "dime",
    0.05: "nickel",
    0.25: "quarter",
    1.00: "1dollar",
    5.00: "5dollar",
}
BILL_SIZE = (120, 55)  # width, height
COIN_SIZE = (60, 60)

RECEIPT_W, RECEIPT_H = 420, 240

# Submit‑button dimensions
BTN_W, BTN_H = 160, 50


# ---------------------------------------------------------------------------
#  MakeChangeTask – limited wallet, manual submit, hidden running total
# ---------------------------------------------------------------------------
class MakeChangeTask(BaseTask):
    def __init__(self, screen: pygame.Surface, items=None, prices=None,
                 max_time_sec: int = 120, max_attempts: int = 3, font=None, **kw):
        super().__init__(screen, subtask_id="make_change_submit", config=kw)
        self.font = font or pygame.font.SysFont(None, 28)

        # --- receipt
        self.items, self.prices, self.total = self._build_receipt(items, prices)

        # --- wallet sprites (limited counts)
        self.wallet_sprites = pygame.sprite.Group()
        self._load_wallet_sprites()

        # --- pay‑zone + buttons
        self.pay_area = self._build_pay_area()
        self.submit_rect = self._build_submit_rect()
        self.surrender_rect = self._build_surrender_rect()

        # --- state
        self.payment_total = 0.0  # not shown to player
        self.max_time = max_time_sec
        self.max_attempts = max_attempts
        self.start_ticks = pygame.time.get_ticks()
        self.clock = pygame.time.Clock()
        self.inactivity_seconds = 0.0
        self.assist_level_used = 0  # Independence Score
        self.process_score = 3  # Process Score
        self.quality_score = 3  # Quality Score
        self.drag_events = 0
        self.extraneous_moves = 0
        self._last_payment_total = 0.0
        self.message_text = ""
        self.show_encouraging_message = False
        self.show_constructive_message = False
        self.show_directive_message = False
        self.drop_item = False  # Flag indicating whether an animated item should be dropped or not
        self._anim_sprite = None  # Placeholder for the Sprite to be animated
        self._anim_step = 0

    # ------------------------------------------------------------------ setup
    def _build_receipt(self, items, prices):
        if items and prices:
            return items, prices, round(sum(prices), 2)
        catalog = [
            ("Campbell’s Tomato Rice soup", 0.79),
            ("Tomato sauce", 0.45),
            ("Local brand Chicken Noodle soup", 0.69),
            ("Local brand Tomato soup", 0.39),
        ]
        items, prices = zip(*random.sample(catalog, 4))
        return list(items), list(prices), round(sum(prices), 2)

    def _build_pay_area(self):
        w, h = 550, 300
        x = self.screen.get_width() - w - 60
        y = self.screen.get_height() - h - 430
        return pygame.Rect(x, y, w, h)

    def _build_submit_rect(self):
        x = self.pay_area.centerx - BTN_W // 2
        y = self.pay_area.bottom + 20
        return pygame.Rect(x, y, BTN_W, BTN_H)

    def _build_surrender_rect(self):
        screen_w, screen_h = self.screen.get_size()
        x = 20  # 20px from the left edge
        y = (screen_h // 2 - BTN_H // 2) - 35
        self.surrender_rect = pygame.Rect(x, y, BTN_W, BTN_H)
        return pygame.Rect(x, y, BTN_W, BTN_H)

    def _load_wallet_sprites(self):
        x_start, y_start = 40, self.screen.get_height() - 140
        x, y = x_start, y_start
        row_spacing = 10
        col_spacing = 10
        max_per_row = 10

        for denom, count in WALLET_COUNTS.items():
            for i in range(count):
                name = DENOM_NAME[denom]
                path = os.path.join(ASSETS_DIR, f"{name}.png")
                try:
                    img = pygame.image.load(path).convert_alpha()
                    img = pygame.transform.smoothscale(img, BILL_SIZE if denom >= 1 else COIN_SIZE)
                except pygame.error:
                    img = pygame.Surface(BILL_SIZE if denom >= 1 else COIN_SIZE)
                    img.fill((190, 190, 190))
                spr = MoneySprite(denom, img, (x, y))
                self.wallet_sprites.add(spr)
                spr.initial_pos = spr.rect.topleft

                # advance grid
                x += spr.rect.width + col_spacing
                if (len(self.wallet_sprites) % max_per_row) == 0:
                    x = x_start
                    y -= (spr.rect.height + row_spacing)

    # -------------------------------------------------------------- event loop
    def _custom_event_handler(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.inactivity_seconds = 0  # activity resets idle timer
            # Check submit first
            if self.submit_rect.collidepoint(event.pos):
                self._handle_submit()
                return
            # Check surrender second
            if self.surrender_rect.collidepoint(event.pos):
                self._handle_surrender()
                return

            clicked = self._sprite_at(event.pos)
            if clicked:
                clicked.dragging = True
                mx, my = event.pos
                ox, oy = clicked.rect.topleft
                clicked.offset = (mx - ox, my - oy)
                self.drag_events += 1

        elif event.type == pygame.MOUSEMOTION:
            for spr in self.wallet_sprites:
                if spr.dragging:
                    mx, my = event.pos
                    ox, oy = spr.offset
                    spr.rect.topleft = (mx - ox, my - oy)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for spr in self.wallet_sprites:
                if spr.dragging:
                    spr.dragging = False
                    was_in = spr.in_pay_area
                    spr.in_pay_area = spr.rect.colliderect(self.pay_area)
                    if was_in and not spr.in_pay_area:
                        self.extraneous_moves += 1
            self._recalc_payment()

    def _sprite_at(self, pos):
        for spr in reversed(self.wallet_sprites.sprites()):
            if spr.rect.collidepoint(pos):
                return spr
        return None

    # ---------------------------------------------------------------- logic

    def _animate_step(self, sprite, step):
        """
        Move `sprite` closer to the pay_area center by `step` pixels per axis.
        Returns True when sprite.center is inside pay_area (and handles drop vs. snap-back).
        """
        tx, ty = self.pay_area.center
        cx, cy = sprite.rect.center

        # Compute next center x
        if abs(tx - cx) <= step:
            new_cx = tx
        else:
            new_cx = cx + step * (1 if tx > cx else -1)

        # Compute next center y
        if abs(ty - cy) <= step:
            new_cy = ty
        else:
            new_cy = cy + step * (1 if ty > cy else -1)

        sprite.rect.center = (new_cx, new_cy)

        # If we've reached the pay area...
        if self.pay_area.collidepoint(sprite.rect.center):
            if self.drop_item:
                # officially drop it in
                sprite.in_pay_area = True
                self._recalc_payment()
            else:
                # snap back to its original slot
                sprite.rect.topleft = sprite.initial_pos
            return True

        return False

    def animate_to_pay(self, sprite, step=2):
        """Start moving `sprite` toward self.pay_area once per update."""
        self._anim_sprite = sprite
        self._anim_step = step

    def swap_sprite_positions(self, spr1: MoneySprite, spr2: MoneySprite):
        # swap live positions
        pos1, pos2 = spr1.rect.topleft, spr2.rect.topleft
        spr1.rect.topleft, spr2.rect.topleft = pos2, pos1

        # swap stored initial positions (for resets)
        if hasattr(spr1, 'initial_pos') and hasattr(spr2, 'initial_pos'):
            spr1.initial_pos, spr2.initial_pos = spr2.initial_pos, spr1.initial_pos

    def pick_highlight(self, amount_left_to_pay):
        # Sort the denominations by numeric value descending
        for value in sorted(DENOM_NAME.keys(), reverse=True):
            if amount_left_to_pay >= value:
                return DENOM_NAME[value]
        # if we get here, nothing fits (e.g. amount_left_to_pay == 0)
        return None

    def _recalc_payment(self):
        self.payment_total = round(sum(s.value for s in self.wallet_sprites if s.in_pay_area), 2)

    def _handle_submit(self):
        success = self.payment_total == self.total
        self._complete(success)

    def _handle_surrender(self):
        difference = abs(self.total - self.payment_total)
        # Threshold for a reasonable attempt ($1.50 but can be changed)
        if difference < 1.5:
            self.assist_level_used = 7
        elif difference < self.payment_total:
            self.assist_level_used = 8
        else:
            self.assist_level_used = 9
        self.process_score = 0
        self._complete(False)

    def _complete(self, success=False):
        # Calculate elapsed time
        elapsed = (pygame.time.get_ticks() - self.start_ticks) / 1000

        # Calculate quality score
        difference = abs(self.total - self.payment_total)
        # Threshold for a reasonable attempt when scoring quality ($1 but can be changed)
        if difference == 0:
            self.quality_score = 3
        elif difference < 1:
            self.quality_score = 2
        elif difference < self.payment_total:
            self.quality_score = 1
        elif difference >= self.payment_total:
            self.quality_score = 0

        self.result_data.update({
            "payment_given": self.payment_total,
            "target_total": self.total,
            "drag_events": self.drag_events,
            "extraneous_moves": self.extraneous_moves,
            "duration_sec": elapsed,
            "independence_score": self.assist_level_used,
            "quality_score": self.quality_score,
            "process_score": self.process_score,
            "success": success,
        })
        self.running = False

    def _update(self):
        dt_ms = self.clock.tick(60)
        self.inactivity_seconds += dt_ms / 1000

        # Independence Score --> 1
        if self.inactivity_seconds > 3 and self.assist_level_used == 0:
            # Tell the _render() method to show the message (Verbal Supportive)
            self.show_encouraging_message = True
            self.assist_level_used = 1  # Update independence score

        # Independence Score --> 2
        if self.inactivity_seconds > 5 and self.assist_level_used == 1:
            self.show_constructive_message = True
            # Tell the _render() method to show a constructive message (Verbal Directive)]
            self.show_encouraging_message = True
            self.assist_level_used = 2  # Update independence score
            self.inactivity_seconds = 0  # Reset inactivity

        # Independence Score --> 3
        if self.inactivity_seconds > 5 and self.assist_level_used == 2:
            # Highlight a money sprite
            amount_left_to_pay = self.total - self.payment_total
            # Find the currency with the largest possible value that can be paid
            highlighted_object = self.pick_highlight(amount_left_to_pay)

            # Highlight a coin/bill that can be added to the pay area
            # find one sprite of that denomination *not already in the pay area*
            for spr in self.wallet_sprites:
                if DENOM_NAME[spr.value] == highlighted_object and not spr.in_pay_area:
                    spr.highlighted = True
                    break

            self.show_encouraging_message = False
            self.process_score = 2  # Update Process Score
            self.assist_level_used = 3  # Update independence score
            self.inactivity_seconds = 0  # Reset inactivity

        # Independence Score --> 4
        if self.inactivity_seconds > 5 and self.assist_level_used == 3:
            # Find the highlighted MoneySprite
            highlighted_spr = None
            for sprite in self.wallet_sprites:
                if sprite.highlighted:
                    highlighted_spr = sprite
                    break
            # Swap it with the MoneySprite closest to the payment area
            self.swap_sprite_positions(highlighted_spr, self.wallet_sprites.sprites()[39])

            self.assist_level_used = 4  # Update independence score
            self.inactivity_seconds = 0  # Reset inactivity

        # Independence Score --> 5
        if self.inactivity_seconds > 5 and self.assist_level_used == 4:
            # Show a message telling the user what do to
            self.show_directive_message = True
            # Move the highlighted MoneySprite to the payment area but DO NOT drop it
            for sprite in self.wallet_sprites:
                if sprite.highlighted:
                    # Animate the MoneySprite
                    self.animate_to_pay(sprite)
                    break
            self.process_score = 1  # Update process score
            self.assist_level_used = 5  # Update independence score
            self.inactivity_seconds = 0  # Reset inactivity

        # Independence Score --> 6
        if self.inactivity_seconds > 5 and self.assist_level_used == 5:
            # Find the biggest MoneySprite available
            for sprite in self.wallet_sprites:
                if sprite.highlighted:
                    # Animate the MoneySprite and DROP IT
                    self.drop_item = True
                    self.animate_to_pay(sprite)
                    break
            self.assist_level_used = 6  # Update independence score
            self.inactivity_seconds = 0  # Reset inactivity

        # timer / attempts
        elapsed = (pygame.time.get_ticks() - self.start_ticks) / 1000
        if elapsed >= self.max_time:
            self.max_attempts -= 1
            if self.max_attempts <= 0:
                self._complete(False)
            else:
                for spr in self.wallet_sprites:
                    spr.rect.topleft = spr.rect.initial if hasattr(spr.rect, 'initial') else spr.rect.topleft
                    spr.in_pay_area = False
                self.payment_total = 0.0
                self.start_ticks = pygame.time.get_ticks()

    # -------------------------------------------------------------- render
    def _render(self):
        self.screen.fill(WHITE)

        # receipt
        margin = 40
        pygame.draw.rect(self.screen, GREY, (margin, margin, RECEIPT_W, RECEIPT_H))
        y = margin + 10
        for item, price in zip(self.items, self.prices):
            txt = self.font.render(f"{item}  ${price:.2f}", True, BLACK)
            self.screen.blit(txt, (margin + 10, y))
            y += txt.get_height() + 4
        total_txt = self.font.render(f"TOTAL: ${self.total:.2f}", True, BLACK)
        self.screen.blit(total_txt, (margin + 10, margin + RECEIPT_H - 30))

        # pay area
        pygame.draw.rect(self.screen, GREY, self.pay_area, border_radius=6)
        label = self.font.render("Drag Here To Pay", True, BLACK)
        self.screen.blit(label, (self.pay_area.centerx - label.get_width() // 2, self.pay_area.top + 6))

        # submit button
        pygame.draw.rect(self.screen, (0, 180, 0), self.submit_rect, border_radius=6)
        btn_lbl = self.font.render("Submit", True, WHITE)
        self.screen.blit(btn_lbl, (self.submit_rect.centerx - btn_lbl.get_width() // 2,
                                   self.submit_rect.centery - btn_lbl.get_height() // 2))

        # surrender button
        pygame.draw.rect(self.screen, (180, 0, 0), self.surrender_rect, border_radius=6)
        btn_lbl = self.font.render("Give Up", True, BLACK)
        lbl_rect = btn_lbl.get_rect(center=self.surrender_rect.center)
        self.screen.blit(btn_lbl, lbl_rect)

        # timer / attempts
        elapsed = int((pygame.time.get_ticks() - self.start_ticks) / 1000)
        timer_txt = self.font.render(f"Time: {self.max_time - elapsed}s  Attempts: {self.max_attempts}", True, BLACK)
        self.screen.blit(timer_txt, (margin, self.screen.get_height() - 40))

        # draw money
        self.wallet_sprites.draw(self.screen)

        # draw red border around any highlighted sprite
        for spr in self.wallet_sprites:
            if spr.highlighted:
                pygame.draw.rect(self.screen, (255, 0, 0), spr.rect, 3)

        if self._anim_sprite:
            done = self._animate_step(self._anim_sprite, self._anim_step)
            if done:
                self._anim_sprite = None

        # draw message if necessary
        if self.show_encouraging_message:
            self.message_text = "You Got This!"
            self._render_message()

        if self.show_constructive_message:
            self.message_text = (f"You have payed ${self.payment_total}, and need to pay "
                                 f"${round(self.total - self.payment_total, 2)} more.")
            self._render_message()

        if self.show_directive_message:
            self.message_text = "Move the highlighted object to the payment area like this ^"
            self._render_message()

        pygame.display.flip()

    def _render_message(self):
        """Draws the assistive message banner across the bottom if needed."""

        # Banner dimensions
        msg_h = 40
        padding = 10
        screen_w, screen_h = self.screen.get_size()
        banner_rect = pygame.Rect(
            0,
            screen_h - msg_h - padding,
            screen_w,
            msg_h,
        )

        # 1) Clear behind the banner
        pygame.draw.rect(self.screen, GREY, banner_rect)

        # 2) Draw the text centered
        txt_surf = self.font.render(self.message_text, True, BLACK)
        txt_rect = txt_surf.get_rect(center=banner_rect.center)
        self.screen.blit(txt_surf, txt_rect)


# ---------------------------------------------------------------------------
#  Quick manual launch (remove in production)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1124, 768))
    task = MakeChangeTask(screen)
    task.run()
    print(task.get_results())
    pygame.quit()
