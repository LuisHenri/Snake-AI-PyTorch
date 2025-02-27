import logging
import random
from collections import deque

import numpy as np
import torch

import game
import helper
from game import SnakeGameAI, Direction, Point
from model import LinearQNet, QTrainer

MAX_MEMORY = 100_000
BATCH_SIZE = 1000
LR = 0.001


class Agent:
    def __init__(self):
        self.n_games = 0
        self.epsilon = 0  # randomness
        self.gamma = 0.9  # discount rate
        self.memory = deque(maxlen=MAX_MEMORY)  # popleft()
        self.model = LinearQNet(8, 64, 3)
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

    @staticmethod
    def get_state(SnakeGame):
        head = SnakeGame.snake[0]
        point_l = Point(head.x - game.BLOCK_SIZE, head.y)
        point_r = Point(head.x + game.BLOCK_SIZE, head.y)
        point_u = Point(head.x, head.y - game.BLOCK_SIZE)
        point_d = Point(head.x, head.y + game.BLOCK_SIZE)

        dir_l = SnakeGame.direction == Direction.LEFT
        dir_r = SnakeGame.direction == Direction.RIGHT
        dir_u = SnakeGame.direction == Direction.UP
        dir_d = SnakeGame.direction == Direction.DOWN

        y = SnakeGame.food.y - SnakeGame.head.y
        x = SnakeGame.food.x - SnakeGame.head.x
        theta = np.arctan2(y, x)
        state = [
            # # Danger straight
            (dir_r and SnakeGame.is_collision(point_r))
            or (dir_l and SnakeGame.is_collision(point_l))
            or (dir_u and SnakeGame.is_collision(point_u))
            or (dir_d and SnakeGame.is_collision(point_d)),
            # # Danger right
            (dir_u and SnakeGame.is_collision(point_r))
            or (dir_d and SnakeGame.is_collision(point_l))
            or (dir_l and SnakeGame.is_collision(point_u))
            or (dir_r and SnakeGame.is_collision(point_d)),
            # # Danger left
            (dir_d and SnakeGame.is_collision(point_r))
            or (dir_u and SnakeGame.is_collision(point_l))
            or (dir_r and SnakeGame.is_collision(point_u))
            or (dir_l and SnakeGame.is_collision(point_d)),
            # Move direction
            dir_l,
            dir_r,
            dir_u,
            dir_d,
            # Food location
            theta,
        ]

        return np.array(state, dtype=float)

    def remember(self, state, action, reward, next_state, done):
        self.memory.append(
            (state, action, reward, next_state, done)
        )  # popleft if MAX_MEMORY is reached

    def train_long_memory(self):
        if len(self.memory) > BATCH_SIZE:
            mini_sample = random.sample(self.memory, BATCH_SIZE)  # list of tuples
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

    def get_action(self, state, frame_iteraction):
        # random moves: tradeoff exploration / exploitation
        self.epsilon = 80 - self.n_games  # NOTE: hardcoded
        final_move = [0, 0, 0]
        if random.randint(0, 200) < self.epsilon:
            move = random.randint(0, 2)
            final_move[move] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)
            move = torch.argmax(prediction).item()
            final_move[move] = 1

        return final_move


def train(model_name="model.pth"):
    plot_scores = []
    plot_mean_scores = []
    total_score = 0
    record = 0
    agent = Agent()
    SnakeGame = SnakeGameAI(400, 400)

    while True:
        # get old state
        state_old = agent.get_state(SnakeGame)

        # get move
        final_move = agent.get_action(state_old, SnakeGame.frame_iteration)

        # perform move and get new state
        reward, done, score = SnakeGame.play_step(final_move)
        state_new = agent.get_state(SnakeGame)

        # train short memory
        agent.train_short_memory(state_old, final_move, reward, state_new, done)

        # remember
        agent.remember(state_old, final_move, reward, state_new, done)

        if done:
            # train long memory, plot result
            SnakeGame.reset()
            agent.n_games += 1
            agent.train_long_memory()

            if score > record:
                record = score
                agent.model.save(model_name)

            print("Game", agent.n_games, "Score", score, "Record:", record)

            plot_scores.append(score)
            total_score += score
            mean_score = total_score / agent.n_games
            plot_mean_scores.append(mean_score)
            helper.plot(plot_scores, plot_mean_scores)


if __name__ == "__main__":
    try:
        train("model8.pth")
    except Exception as err:
        logging.error(err, exc_info=True)
