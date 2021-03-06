import sys
import os 

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(dir_path, '../'))
sys.path.append(os.path.join(dir_path, './ai'))
sys.path.append(os.path.join(dir_path, './computer_vision'))
sys.path.append(os.path.join(dir_path, './game_logic'))
sys.path.append(os.path.join(dir_path, './movement'))

import threading
import numpy as np
import time

from robot.ai.ai_player import *
from robot.computer_vision.camera import CameraHandler, camera_config
from robot.game_logic.checkers import Checkers, Move
from robot.movement.driver import MovementHandler, driver_config

class RobotCheckers(object):
    def __init__(self, debug=0):
        self.__debug = debug

        self.__movement_handler = MovementHandler()
        self.__camera_handler = CameraHandler(debug)
        self.__robot_thread = threading.Thread(target=self.__robot_handler)

        self.__checkers = None
        self.__robot_color = None
        self.__ai_player = None
        self.__play = False
        self.__game_initialized = False
        self.__move_done = True

        self.__player_move_valid = True
        self.__robot_arm_moving = False
        self.__run = True
    
    @property
    def calibrated(self):
        return self.__camera_handler.initialized and self.__movement_handler.calibrated
        
    @property
    def driver_calibrated(self):
        return self.__movement_handler.calibrated
        
    @property
    def camera_calibrated(self):
        return self.__camera_handler.initialized
    
    @property
    def board_from_checkers(self):
        if self.__checkers is None or self.__ai_player is None:
            return None
        return self.__checkers.board
    
    @property
    def board_from_camera(self):
        return self.__camera_handler.read_board()[0]
    
    @property
    def all_moves(self):
        if self.__checkers is not None:
            return self.__checkers.all_moves
        return None
    
    @property
    def turn_counter(self):
        if self.__checkers is not None:
            return self.__checkers.turn_counter
        return None

    @property
    def move_done(self):
        return self.__move_done
    
    @property
    def winner(self):
        if self.__checkers is not None:
            return self.__checkers.winner
        return None
    
    @property
    def player_turn(self):
        if self.__checkers is not None:
            return self.__checkers.player_turn != self.__ai_player.num
        return None
    
    @property
    def player_move_valid(self):
        return self.__player_move_valid
    
    @property
    def player_available_moves(self):
        if self.__checkers is not None:
            return self.__checkers.calc_available_moves_for_player(
                self.__checkers.oponent(self.__ai_player.num))
        return None
    
    @property
    def checkers_end(self):
        if self.__checkers is not None:
            return self.__checkers.end
        return None
    
    @property
    def queens_moves_to_draw(self):
        if self.__checkers is not None:
            return self.__checkers.queens_moves_to_draw(self)
        return None
    
    def start(self):
        self.__movement_handler.start()
        self.__camera_handler.start()
    
        self.__robot_thread.start()
    
    def stop(self):
        self.__run = False

        self.__robot_thread.join()

        self.__camera_handler.stop()
        self.__movement_handler.stop()

    def initialize_game(self, robot_color, difficulty, automatic_pawns_placement_on_start=True, board=None, turn=None):
        self.__robot_color = robot_color

        self.__checkers = Checkers(robot_color, board, turn)

        if difficulty == 1:
            # random
            self.__ai_player = AIPlayerRandom(robot_color)
        elif difficulty <= 4:
            # MonteCarlo with 10, 20, 30 simulations per move
            self.__ai_player = AIPlayerMonteCarlo(robot_color, (difficulty - 1)*10)
        elif difficulty <= 7:
            # Minimax with depth of 2, 3, 4
            self.__ai_player = AIPlayerMinimax(robot_color, difficulty - 3)
        else:
            # Alpha-beta with depth of 5, 6, 7
            self.__ai_player = AIPlayerAlphaBeta(robot_color, difficulty - 3)

        # board preparation
        if automatic_pawns_placement_on_start:
            print('Robot will place pawns on board')
            self.__prepare_board()
        else:
            print('Player had to place pawns on board')
            while True:
                if np.all(self.board_from_camera == self.board_from_checkers):
                    break
                time.sleep(.5)
        print('Board prepared to start game')
    
    def start_game(self):
        print('Game started')
        if self.__checkers is not None:
            self.__play = True
        
    def abort_game(self):
        if self.__checkers is not None:
            self.__play = False
            self.__checkers = None
            self.__movement_handler.interrupt()
            while not self.__movement_handler.all_done:
                time.sleep(1)
            self.__movement_handler.put_pawn()
            self.__movement_handler.move_to_corner(1, -1)

    def pause_robot(self):
        self.__movement_handler.pause()

    def unpause_robot(self):
        self.__movement_handler.unpause()

    def is_robot_paused(self):
        return self.__movement_handler.pause_status

    def __robot_handler(self):
        # calibration

        self.__movement_handler.calibrate()
        self.__movement_handler.move_to_corner(1, -1)

        while not (self.__camera_handler.initialized and self.__movement_handler.calibrated) and self.__run:
            # awaiting submodules calibration
            time.sleep(1)
        
        # main robot loop
        while self.__run:
            time.sleep(.1)
            if self.__play == False or self.__checkers is None:
                # no game to play
                continue
            
            while self.__checkers is not None and not self.__checkers.end:
                time.sleep(.1)
                if self.__checkers is None:
                    break
                if self.__checkers is not None and self.__checkers.player_turn == self.__ai_player.num:
                    self.__move_done = False
                    robot_move, _, promoted = self.__ai_player.make_move(self.__checkers)
                    self.__make_move(robot_move, promoted)
                    self.__move_done = True
                else:
                    player_move = self.__get_player_move()

                    if player_move is not None and self.__checkers is not None and self.__checkers.is_move_valid(player_move):
                        self.__player_move_valid = True
                        self.__checkers.make_move(player_move)

                    else:
                        self.__player_move_valid = False
            
            self.__play = False
            self.__checkers = None

    def __get_player_move(self):
        timer = None
        board_code = None

        while self.__run:
            board_code, _, _, hand_above_board = self.__camera_handler.read_board()

            if not hand_above_board:
                if timer is None:
                    timer = time.perf_counter()
                elif time.perf_counter() - timer > 1:
                    break

            else:
                timer = None
                
            time.sleep(.1)
        
        if board_code is None:
            return None

        return self.__checkers.calc_move_between_boards(board_code)

    def __make_move(self, move, promoted):
        board_pos = None
        free_figures = None

        while self.__run:
            _, board_pos, free_figures, _ = self.__camera_handler.read_board()

            if np.abs(board_pos[move.src]).sum() > 1.e-5:
                break
                
            time.sleep(.1)

        self.__robot_arm_moving = True
        def interrupt_thread_fun():
            interrupted = False
            while self.__robot_arm_moving and self.__run:
                _, _, _, hand_above_board = self.__camera_handler.read_board()
                if hand_above_board and not interrupted:
                    self.__movement_handler.pause()
                    interrupted = True
                
                if not hand_above_board and interrupted:
                    self.__movement_handler.unpause()
                    interrupted = False

                time.sleep(.1)
        
        interrupt_thread = threading.Thread(target=interrupt_thread_fun)
        interrupt_thread.start()
        
        # move selected figure
        self.__movement_handler.move_pawn_from_pos_to_square(*self.__cam_pos_to_drv_pos(board_pos[move.src]),
                                                             *move.dest)
        # remove taken figures
        for figrure_pos in move.taken_figures:
            free_pos = self.__camera_handler.find_free_pos_outside_board()
            self.__movement_handler.move_pawn_from_pos_to_pos(*self.__cam_pos_to_drv_pos(board_pos[figrure_pos]),
                                                              *self.__cam_pos_to_drv_pos(free_pos))
        
        # promote pawn
        if promoted:
            free_pos = self.__camera_handler.find_free_pos_outside_board()
            self.__movement_handler.move_pawn_from_square_to_pos(*move.dest,
                                                                 *self.__cam_pos_to_drv_pos(free_pos))

            if self.__robot_color == 0:
                queen_pos = free_figures[2][0]
            else:
                queen_pos = free_figures[4][0]

            self.__movement_handler.move_pawn_from_pos_to_square(*self.__cam_pos_to_drv_pos(queen_pos),
                                                                 *move.dest)
        
        # move to corner
        self.__movement_handler.move_to_corner(1, -1)

        time.sleep(1)

        while not self.__movement_handler.all_done and self.__run:
            # wait for moves to be done
            time.sleep(.1)

        self.__robot_arm_moving = False
        interrupt_thread.join()
    
    def __prepare_board(self):
        board_code = None
        board_pos = None
        free_figures = None
        timer = None

        self.__robot_arm_moving = True

        def interrupt_thread_fun():
            interrupted = False
            while self.__robot_arm_moving and self.__run:
                _, _, _, hand_above_board = self.__camera_handler.read_board()
                if hand_above_board and not interrupted:
                    self.__movement_handler.pause()
                    interrupted = True
                
                if not hand_above_board and interrupted:
                    self.__movement_handler.unpause()
                    interrupted = False
                
                time.sleep(.1)
        
        interrupt_thread = threading.Thread(target=interrupt_thread_fun)
        interrupt_thread.start()

        time.sleep(1)

        while not self.__movement_handler.all_done and self.__run:
            time.sleep(.1)

        needed_figures = {}

        for i in range(1, 5):
            needed_figures[i] = (self.__checkers.board == i).sum()

        while self.__run:
            time.sleep(.1)
            board_code, board_pos, free_figures, hand_above_board = self.__camera_handler.read_board()
            
            if not hand_above_board:
                if timer is None:
                    timer = time.perf_counter()
                elif time.perf_counter() - timer > 5:
                    all_needed_figures_available = True
                    for i in range(1, 5):
                        if needed_figures[i] > len(free_figures[i]):
                            all_needed_figures_available = False
                            break
                    if all_needed_figures_available:
                        break

            else:
                timer = None
            
            time.sleep(.1)
        
        if not self.__run:
            return

        to_remove = []
        to_move = []
        free_figures_indices = [0, 0, 0, 0]

        for x in range(8):
            for y in range(8):
                curr = board_code[x, y]
                target = self.__checkers.board[x, y]
                if target != curr:
                    if curr != 0:
                        to_remove.append(self.__cam_pos_to_drv_pos(board_pos[x, y]))

                    if target != 0:
                        free_figure_pos = free_figures[target][free_figures_indices[target - 1]]
                        to_move.append((*self.__cam_pos_to_drv_pos(free_figure_pos), x, y))

                        free_figures_indices[target - 1] += 1

        for x, y in to_remove:
            free_pos = self.__camera_handler.find_free_pos_outside_board()
            self.__movement_handler.move_pawn_from_pos_to_pos(x, y, *free_pos)

        for f_x, f_y, x, y in to_move:
            self.__movement_handler.move_pawn_from_pos_to_square(f_x, f_y, x, y)
        
        time.sleep(1)

        # move to corner
        self.__movement_handler.move_to_corner(1, -1)

        time.sleep(1)
        
        while not self.__movement_handler.all_done and self.__run:
            # wait for moves to be done
            time.sleep(.1)

        self.__robot_arm_moving = False
        interrupt_thread.join()
    
    @staticmethod
    def __cam_pos_to_drv_pos(pos, offset=True):
        return (driver_config.square_size*pos[0], driver_config.square_size*pos[1])
