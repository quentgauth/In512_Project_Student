__author__ = "Aybuke Ozturk Suri, Johvany Gustave"
__copyright__ = "Copyright 2023, IN512, IPSA 2024"
__credits__ = ["Aybuke Ozturk Suri", "Johvany Gustave"]
__license__ = "Apache License 2.0"
__version__ = "1.0.0"

import pygame, os
from my_constants import * 

img_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "img")


class GUI:
    def __init__(self, game, fps=10, cell_size=40):
        self.game = game
        self.w, self.h = self.game.map_w, self.game.map_h
        self.fps = fps
        self.clock = pygame.time.Clock()
        self.cell_size = cell_size
        self.screen_res = (self.w*cell_size, self.h*cell_size)      


    def on_init(self):
        pygame.init()
        self.screen = pygame.display.set_mode(self.screen_res)
        pygame.display.set_icon(pygame.image.load(img_folder + "/icon.png"))
        pygame.display.set_caption("IN512 Project")
        self.create_items()        
        self.running = True


    def create_items(self):
        #box
        box_img = pygame.image.load(img_folder + "/box.png")
        box_img = pygame.transform.scale(box_img, (self.cell_size, self.cell_size))
        self.boxes = [box_img.copy() for _ in range(self.game.nb_agents)]
        #keys
        key_img = pygame.image.load(img_folder + "/key.png")
        key_img = pygame.transform.scale(key_img, (self.cell_size, self.cell_size))
        self.keys = [key_img.copy() for _ in range(self.game.nb_agents)]
        #agent text number
        font = pygame.font.SysFont("Arial", self.cell_size//4, True)
        self.text_agents = [font.render(f"{i+1}", True, self.game.agents[i].color) for i in range(self.game.nb_agents)]
        #agent_img
        agent_img = pygame.image.load(img_folder + "/robot.png")
        agent_img = pygame.transform.scale(agent_img, (self.cell_size, self.cell_size))
        self.agents = [agent_img.copy() for _ in range(self.game.nb_agents)]

    
    def on_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False

    
    def on_cleanup(self):
        pygame.event.pump()
        pygame.quit()
    

    def render(self):
        try:
            self.on_init()
            while self.running:
                for event in pygame.event.get():
                    self.on_event(event)    
                self.draw()
                self.clock.tick(self.fps)
            self.on_cleanup()
        except Exception:
            pass
    

    def draw(self):
        self.screen.fill(BG_COLOR)
        
        # Draw walls and warning zones
        for wall in self.game.walls:
            # Warning zone (light gray)
            for wx, wy in wall.get_warning_zone():
                if 0 <= wx < self.w and 0 <= wy < self.h:
                    pygame.draw.rect(self.screen, (200, 200, 200), (wx*self.cell_size, wy*self.cell_size, self.cell_size, self.cell_size))
            # Wall cells (dark gray)
            for wx, wy in wall.cells:
                if 0 <= wx < self.w and 0 <= wy < self.h:
                    pygame.draw.rect(self.screen, (80, 80, 80), (wx*self.cell_size, wy*self.cell_size, self.cell_size, self.cell_size))
        
        #Grid
        for i in range(1, self.h):
            pygame.draw.line(self.screen, BLACK, (0, i*self.cell_size), (self.w*self.cell_size, i*self.cell_size))
        for j in range(1, self.w):
            pygame.draw.line(self.screen, BLACK, (j*self.cell_size, 0), (j*self.cell_size, self.h*self.cell_size))

        for i in range(self.game.nb_agents):
            #agent_paths
            for x, y in self.game.agent_paths[i]:
                pygame.draw.rect(self.screen, self.game.agents[i].color, (x*self.cell_size, y*self.cell_size, self.cell_size, self.cell_size))

        for i in range(self.game.nb_agents):            
            #keys
            pygame.draw.rect(self.screen, self.game.agents[i].color, (self.game.keys[i].x*self.cell_size, self.game.keys[i].y*self.cell_size, self.cell_size, self.cell_size), width=3)
            self.screen.blit(self.keys[i], self.keys[i].get_rect(topleft=(self.game.keys[i].x*self.cell_size, self.game.keys[i].y*self.cell_size)))
            
            #boxes
            pygame.draw.rect(self.screen, self.game.agents[i].color, (self.game.boxes[i].x*self.cell_size, self.game.boxes[i].y*self.cell_size, self.cell_size, self.cell_size), width=3)
            self.screen.blit(self.boxes[i], self.boxes[i].get_rect(topleft=(self.game.boxes[i].x*self.cell_size, self.game.boxes[i].y*self.cell_size)))
            
            #agents
            self.screen.blit(self.agents[i], self.agents[i].get_rect(center=(self.game.agents[i].x*self.cell_size + self.cell_size//2, self.game.agents[i].y*self.cell_size + self.cell_size//2)))
            self.screen.blit(self.text_agents[i], self.text_agents[i].get_rect(center=(self.game.agents[i].x*self.cell_size + self.cell_size-self.text_agents[i].get_width()//2, self.game.agents[i].y*self.cell_size + self.text_agents[i].get_height()//2)))

        # Draw red cross if game over
        if self.game.game_over and self.game.death_position:
            dx, dy = self.game.death_position
            x, y = dx * self.cell_size, dy * self.cell_size
            # Draw a big red X on the wall cell where agent died
            pygame.draw.line(self.screen, RED, (x + 2, y + 2), (x + self.cell_size - 2, y + self.cell_size - 2), 4)
            pygame.draw.line(self.screen, RED, (x + self.cell_size - 2, y + 2), (x + 2, y + self.cell_size - 2), 4)
            
            # Draw "GAME OVER" text in center of screen
            font = pygame.font.SysFont("Arial", self.cell_size * 2, True)
            text = font.render("GAME OVER", True, RED)
            text_rect = text.get_rect(center=(self.screen_res[0] // 2, self.screen_res[1] // 2))
            # Draw black background for text
            bg_rect = text_rect.inflate(20, 10)
            pygame.draw.rect(self.screen, BLACK, bg_rect)
            self.screen.blit(text, text_rect)

        pygame.display.update()