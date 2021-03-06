import sys
import os 

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(dir_path, '../../../'))

import random

import src.robot.ai.minimax as minimax
import src.robot.ai.monte_carlo as monte_carlo
import src.robot.ai.alphabeta as alphabeta
import src.robot.ai.neural_network as neural_network

class __AIPlayer(object):
    def __init__(self, num):
        self.__num = num

    @property
    def num(self):
        return self.__num

    def make_move(self, checkers):
        pass

class AIPlayerRandom(__AIPlayer):
    def make_move(self, checkers):
        available_moves = checkers.calc_available_moves_for_player(self.num)
        move = random.choice(available_moves)

        ret, promoted = checkers.make_move(move)
        
        return move, ret, promoted
    
    def __repr__(self):
        return 'AIPlayerRandom()'
        
class AIPlayerAlphaBeta(__AIPlayer):
    def __init__(self, num, max_depth):
        super(AIPlayerAlphaBeta, self).__init__(num)
        self.__max_depth = max_depth

    def make_move(self, checkers):
        move = alphabeta.get_best_move(checkers, self.__max_depth)

        ret, promoted = checkers.make_move(move)
        
        return move, ret, promoted

    def __repr__(self):
        return f'AIPlayerAlphaBeta(depth={self.__max_depth})'

class AIPlayerMinimax(__AIPlayer):
    def __init__(self, num, max_depth):
        super(AIPlayerMinimax, self).__init__(num)
        self.__max_depth = max_depth

    def make_move(self, checkers):
        move = minimax.get_best_move(checkers, self.__max_depth)

        ret, promoted = checkers.make_move(move)
        
        return move, ret, promoted

    def __repr__(self):
        return f'AIPlayerMinimax(depth={self.__max_depth})'
        
class AIPlayerMonteCarlo(__AIPlayer):
    def __init__(self, num, simulations):
        super(AIPlayerMonteCarlo, self).__init__(num)
        self.__simulations = simulations

    def make_move(self, checkers):
        move = monte_carlo.get_best_move(checkers, self.__simulations)
        
        ret, promoted = checkers.make_move(move)
        
        return move, ret, promoted

    def __repr__(self):
        return f'AIPlayerMonteCarlo(simulations={self.__simulations})'

class AIPlayerNeuralNetwork(__AIPlayer):
    def __init__(self, num, network_folder):
        super(AIPlayerNeuralNetwork, self).__init__(num)
        self.__network = neural_network.get_network(network_folder)
    
    def make_move(self, checkers):
        move = self.__network.get_best_move(checkers)
        
        ret, promoted = checkers.make_move(move)
        
        return move, ret, promoted
        
    def __repr__(self):
        return 'AIPlayerNeuralNetwork()'