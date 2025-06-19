import pygame
import time

class BaseTask:
    def __init__(self, screen, subtask_id="base_task", config=None):
        """
        Initialize the task.

        Args:
            screen (pygame.Surface): The main screen surface for drawing.
            task_id (str): Unique identifier for the task.
            config (dict): Optional configuration for task parameters.
        """
        self.screen = screen
        self.subtask_id = subtask_id
        self.config = config or {}

        self.running = True
        self.clock = pygame.time.Clock()
        self.start_time = None
        self.end_time = None
        self.result_data = {
            "subtask_id": self.subtask_id,
            "start_time": None,
            "end_time": None,
            "duration_sec": None,
            "errors": [], # String list of errors (use emptystr [str()] for unknown error), len(errors) = # of errors
            "independence_score": None,
            "quality_score": None,
            "process_score": None,
        }

    def run(self):
        """Main loop for the task."""
        self.start_time = time.time()
        self.result_data["start_time"] = self.start_time

        while self.running:
            self._handle_events()
            self._update()
            self._render()
            self.clock.tick(60)  # Maintain 60 FPS

        self.end_time = time.time()
        self.result_data["end_time"] = self.end_time
        self.result_data["duration_sec"] = round(self.end_time - self.start_time, 2)

    def _handle_events(self):
        """Process Pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            self._custom_event_handler(event)

    def _custom_event_handler(self, event):
        """Override this to handle custom events in derived tasks."""
        pass

    def _update(self):
        """Override this to update task state per frame."""
        pass

    def _render(self):
        """Override this to draw the screen."""
        self.screen.fill((255, 255, 255))
        pygame.display.flip()

    def get_results(self):
        """
        Return a dictionary of task results.

        Returns:
            dict: Summary of task performance data.
        """
        return self.result_data


"""pygame.init()
screen = pygame.display.set_mode((1024, 768))
task = MakeChangeTask(screen)
task.run()
print(task.get_results())
pygame.quit()"""