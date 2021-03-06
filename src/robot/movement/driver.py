import sys
import os 

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(dir_path, '../../../'))

from RPi import GPIO
import traceback
import threading
import datetime
import time

import src.robot.movement.driver_config as driver_config

class MovementHandler(object):
    def __init__(self):
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(driver_config.pin_endstop_X_min, GPIO.IN)
        GPIO.setup(driver_config.pin_endstop_X_max, GPIO.IN)
        GPIO.setup(driver_config.pin_endstop_Y_min, GPIO.IN)
        GPIO.setup(driver_config.pin_endstop_Y_max, GPIO.IN)

        GPIO.setup(driver_config.pin_motor_A_step, GPIO.OUT)
        GPIO.setup(driver_config.pin_motor_A_dir, GPIO.OUT)
        GPIO.setup(driver_config.pin_motor_B_step, GPIO.OUT)
        GPIO.setup(driver_config.pin_motor_B_dir, GPIO.OUT)
        
        GPIO.output(driver_config.pin_motor_A_step, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_A_dir, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_dir, GPIO.LOW)

        GPIO.setup(driver_config.pin_magnet, GPIO.OUT)
        
        GPIO.output(driver_config.pin_magnet, GPIO.LOW)

        GPIO.setup(driver_config.pin_servo, GPIO.OUT)
        
        self.__servo_pwm = GPIO.PWM(driver_config.pin_servo, driver_config.servo_rate)
        self.__servo_pwm.start(0)

        self.__pos = [0, 0]
        self.__X_range = [0, 0]
        self.__Y_range = [0, 0]
        self.__calibrated = False
        self.__run = True
        self.__instr_list = []
        self.__instr_handler_thread = threading.Thread(target=self.__instr_handler)
        self.__speed = driver_config.max_speed
        self.__all_done = True
        self.__interrupt = False
        self.__pause = False

    @property
    def pos(self):
        return (self.__pos[0]/driver_config.steps_per_cm - driver_config.board_pos['x'][0],
                self.__pos[1]/driver_config.steps_per_cm - driver_config.board_pos['y'][0])

    @property
    def X_range(self):
        return (self.__X_range[0]/driver_config.steps_per_cm - driver_config.board_pos['x'][0],
                self.__X_range[1]/driver_config.steps_per_cm - driver_config.board_pos['x'][0])

    @property
    def Y_range(self):
        return (self.__Y_range[0]/driver_config.steps_per_cm - driver_config.board_pos['y'][0],
                self.__Y_range[1]/driver_config.steps_per_cm - driver_config.board_pos['y'][0])
    
    @property
    def calibrated(self):
        return self.__calibrated
    
    @property
    def all_done(self):
        return self.__all_done

    def start(self):
        self.__instr_handler_thread.start()

    def stop(self):
        self.__run = False

        self.__instr_handler_thread.join()

        self.__servo_pwm.stop()

        GPIO.cleanup()

    def endstop_state(self, axis, end):
        if axis == 'X':
            if end == 0:
                return GPIO.input(driver_config.pin_endstop_X_min)
            if end == 1:
                return GPIO.input(driver_config.pin_endstop_X_max)
        if axis == 'Y':
            if end == 0:
                return GPIO.input(driver_config.pin_endstop_Y_min)
            if end == 1:
                return GPIO.input(driver_config.pin_endstop_Y_max)

    def step_X_forward(self):
        self.__instr_list.append(f'sxf')

    def step_X_backward(self):
        self.__instr_list.append(f'sxb')
    
    def step_Y_forward(self):
        self.__instr_list.append(f'syf')

    def step_Y_backward(self):
        self.__instr_list.append(f'syb')
    
    def move_to_pos(self, x, y):
        self.__instr_list.append(f'mtp {x} {y}')

    def move_to_square(self, row, col):
        self.__instr_list.append(f'mts {row} {col}')
    
    def move_to_corner(self, x, y):
        self.__instr_list.append(f'mtc {x} {y}')

    def set_magnet(self, state):
        self.__instr_list.append(f'sm {state}')

    def set_servo(self, value):
        self.__instr_list.append(f'ss {value}')
    
    def put_pawn(self):
        self.__instr_list.append(f'pp')

    def take_pawn(self):
        self.__instr_list.append(f'tp')
    
    def move_pawn_from_square_to_square(self, from_col, from_row, to_col, to_row):
        self.__instr_list.append(f'mpfsts {from_col} {from_row} {to_col} {to_row}')

    def move_pawn_from_square_to_pos(self, from_col, from_row, to_x, to_y):
        self.__instr_list.append(f'mpfstp {from_col} {from_row} {to_x} {to_y}')

    def move_pawn_from_pos_to_square(self, from_x, from_y, to_col, to_row):
        self.__instr_list.append(f'mpfpts {from_x} {from_y} {to_col} {to_row}')

    def move_pawn_from_pos_to_pos(self, from_x, from_y, to_x, to_y):
        self.__instr_list.append(f'mpfptp {from_x} {from_y} {to_x} {to_y}')

    def calibrate(self):
        self.__instr_list.append(f'c')

    def interrupt(self):
        self.__interrupt = True

    def pause(self):
        self.__pause = True

    def unpause(self):
        self.__pause = False

    @property
    def pause_status(self):
        return self.__pause

    def __instr_handler(self):
        while self.__run:
            if len(self.__instr_list):
                self.__all_done = False
                try:
                    instr = self.__instr_list.pop(0).split()
                    if instr[0] == 'mtp':
                        self.__move_to_pos_inner(float(instr[1]), float(instr[2]))

                    elif instr[0] == 'mts':
                        self.__move_to_square_inner(int(instr[1]), int(instr[2]))

                    elif instr[0] == 'mtc':
                        self.__move_to_corner_inner(int(instr[1]), int(instr[2]))
                    
                    elif instr[0] == 'sxf':
                        self.__step_X_forward_inner()
                    
                    elif instr[0] == 'sxb':
                        self.__step_X_backward_inner()
                    
                    elif instr[0] == 'syf':
                        self.__step_Y_forward_inner()
                    
                    elif instr[0] == 'syb':
                        self.__step_Y_backward_inner()
                    
                    elif instr[0] == 'sm':
                        self.__set_magnet_inner(int(instr[1]))
                        
                    elif instr[0] == 'ss':
                        self.__set_servo_inner(int(instr[1]))
                        
                    elif instr[0] == 'pp':
                        self.__put_pawn_inner()
                        
                    elif instr[0] == 'tp':
                        self.__take_pawn_inner()
                        
                    elif instr[0] == 'mpfsts':
                        self.__move_pawn_from_square_to_square_inner(int(instr[1]), int(instr[2]), int(instr[3]), int(instr[4]))
                        
                    elif instr[0] == 'mpfstp':
                        self.__move_pawn_from_square_to_pos_inner(int(instr[1]), int(instr[2]), float(instr[3]), float(instr[4]))
                        
                    elif instr[0] == 'mpfpts':
                        self.__move_pawn_from_pos_to_square_inner(float(instr[1]), float(instr[2]), int(instr[3]), int(instr[4]))
                        
                    elif instr[0] == 'mpfptp':
                        self.__move_pawn_from_pos_to_pos_inner(float(instr[1]), float(instr[2]), float(instr[3]), float(instr[4]))

                    elif instr[0] == 'c':
                        self.__calibrate_inner()
                    
                    else:
                        self.__log(f'Unknown instruction: {instr}')

                    if self.__interrupt:
                        self.__instr_list.clear()
                        self.__interrupt = False

                except Exception as ex:
                    self.__log(f'Instr handling error: {traceback.format_exc()}')
            
            else:
                self.__all_done = True
            
            time.sleep(.1)

    def __step_X_forward_inner(self):
        if self.__pos[0] >= self.__X_range[1]:
            return
        GPIO.output(driver_config.pin_motor_A_dir, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_B_dir, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.HIGH)
        time.sleep(1./self.__speed)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.LOW)
        time.sleep(1./self.__speed)
        self.__pos[0] += 1

    def __step_X_backward_inner(self):
        if self.__pos[0] <= self.__X_range[0]:
            return
        GPIO.output(driver_config.pin_motor_A_dir, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_dir, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.HIGH)
        time.sleep(1./self.__speed)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.LOW)
        time.sleep(1./self.__speed)
        self.__pos[0] -= 1
    
    def __step_Y_forward_inner(self):
        if self.__pos[1] >= self.__Y_range[1]:
            return
        GPIO.output(driver_config.pin_motor_A_dir, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_dir, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.HIGH)
        time.sleep(1./self.__speed)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.LOW)
        time.sleep(1./self.__speed)
        self.__pos[1] += 1

    def __step_Y_backward_inner(self):
        if self.__pos[1] <= self.__Y_range[0]:
            return
        GPIO.output(driver_config.pin_motor_A_dir, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_B_dir, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.HIGH)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.HIGH)
        time.sleep(1./self.__speed)
        GPIO.output(driver_config.pin_motor_A_step, GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_step, GPIO.LOW)
        time.sleep(1./self.__speed)
        self.__pos[1] -= 1

    def __move_to_pos_inner(self, x, y):
        step_x = int((x + driver_config.board_pos['x'][0])*driver_config.steps_per_cm)
        step_y = int((y + driver_config.board_pos['y'][0])*driver_config.steps_per_cm)

        if step_x < self.__X_range[0]:
            step_x = self.__X_range[0]
        if step_x > self.__X_range[1]:
            step_x = self.__X_range[1]

        if step_y < self.__Y_range[0]:
            step_y = self.__Y_range[0]
        if step_y > self.__Y_range[1]:
            step_y = self.__Y_range[1]

        delta_x = step_x - self.__pos[0]
        delta_y = step_y - self.__pos[1]
        
        delta_a = delta_x - delta_y
        delta_b = delta_x + delta_y

        GPIO.output(driver_config.pin_motor_A_dir, GPIO.HIGH if delta_a > 0 else GPIO.LOW)
        GPIO.output(driver_config.pin_motor_B_dir, GPIO.HIGH if delta_b > 0 else GPIO.LOW)

        dir_a = (-1, 1)[delta_a > 0]
        dir_b = (-1, 1)[delta_b > 0]

        delta_a = abs(delta_a)
        delta_b = abs(delta_b)

        def __move_motor(motor_pin, steps, speed, steps_done):
            for i in range(steps):
                steps_done[0] = i
                while self.__pause:
                    time.sleep(.01)

                if self.__interrupt:
                    break

                GPIO.output(motor_pin, GPIO.HIGH)
                time.sleep(1./speed)
                GPIO.output(motor_pin, GPIO.LOW)
                time.sleep(1./speed)

        thread_a_steps_done = [0]
        thread_b_steps_done = [0]
        
        thread_a = threading.Thread(target=__move_motor, args=(driver_config.pin_motor_A_step, delta_a, self.__speed, thread_a_steps_done))
        thread_b = threading.Thread(target=__move_motor, args=(driver_config.pin_motor_B_step, delta_b, self.__speed, thread_b_steps_done))

        thread_a.start()
        thread_b.start()

        thread_a.join()
        thread_b.join()

        if self.__interrupt:
            delta_a_done = thread_a_steps_done[0]*dir_a
            delta_b_done = thread_b_steps_done[0]*dir_b

            delta_x_done = (delta_b_done + delta_a_done)//2
            delta_y_done = (delta_b_done - delta_a_done)//2

            self.__pos[0] += delta_x_done
            self.__pos[1] += delta_y_done

        else:
            self.__pos[0] += delta_x
            self.__pos[1] += delta_y

    def __move_to_square_inner(self, col, row):
        if row < 0 or row > 7:
            raise Exception(f'Wrong row: {row}')

        if col < 0 or col > 7:
            raise Exception(f'Wrong column: {col}')

        x_m = col/8
        y_m = row/8

        x = driver_config.square_size/2 +\
            x_m*(driver_config.board_pos['x'][1] - driver_config.board_pos['x'][0])
        y = driver_config.square_size/2 +\
            y_m*(driver_config.board_pos['y'][1] - driver_config.board_pos['y'][0])

        self.__move_to_pos_inner(x, y)
    
    def __move_to_corner_inner(self, x, y):
        x = (-1, 1)[x > 0]
        y = (-1, 1)[y > 0]

        motor_to_move = None
        dir_a = 0
        dir_b = 0
        if y == x:
            dir_b = (-1, 1)[x > 0]
            GPIO.output(driver_config.pin_motor_B_dir, GPIO.HIGH if dir_b > 0 else GPIO.LOW)
            motor_to_move = 'B'
        else:
            dir_a = (-1, 1)[x > 0]
            GPIO.output(driver_config.pin_motor_A_dir, GPIO.HIGH if dir_a > 0 else GPIO.LOW)
            motor_to_move = 'A'
        
        endstop_x = (driver_config.pin_endstop_X_min, driver_config.pin_endstop_X_max)[x > 0]
        endstop_y = (driver_config.pin_endstop_Y_min, driver_config.pin_endstop_Y_max)[y > 0]
        motor_pin = (driver_config.pin_motor_A_step, driver_config.pin_motor_B_step)[motor_to_move == 'B']

        endstop_triggered = None
        steps_done = {'A': 0, 'B': 0}
        while not self.__interrupt:
            if GPIO.input(endstop_x):
                endstop_triggered = 'x'
                break

            if GPIO.input(endstop_y):
                endstop_triggered = 'y'
                break

            GPIO.output(motor_pin, GPIO.HIGH)
            time.sleep(1./self.__speed)
            GPIO.output(motor_pin, GPIO.LOW)
            time.sleep(1./self.__speed)

            steps_done[motor_to_move] += 1

            while self.__pause:
                time.sleep(.01)
        
        if motor_to_move == 'A':
            if endstop_triggered == 'x':
                dir_a = (-1, 1)[y > 0]
            elif endstop_triggered == 'y':
                dir_a = (-1, 1)[x > 0]
            GPIO.output(driver_config.pin_motor_B_dir, GPIO.HIGH if dir_a > 0 else GPIO.LOW)
        elif motor_to_move == 'B':
            if endstop_triggered == 'x':
                dir_b = (-1, 1)[y < 0]
            elif endstop_triggered == 'y':
                dir_b = (-1, 1)[x > 0]
            GPIO.output(driver_config.pin_motor_A_dir, GPIO.HIGH if dir_b > 0 else GPIO.LOW)
        
        while not self.__interrupt:
            if GPIO.input(endstop_x) and GPIO.input(endstop_y):
                break

            GPIO.output(driver_config.pin_motor_A_step, GPIO.HIGH)
            GPIO.output(driver_config.pin_motor_B_step, GPIO.HIGH)
            time.sleep(1./self.__speed)
            GPIO.output(driver_config.pin_motor_A_step, GPIO.LOW)
            GPIO.output(driver_config.pin_motor_B_step, GPIO.LOW)
            time.sleep(1./self.__speed)

            steps_done['A'] += 1
            steps_done['B'] += 1

            while self.__pause:
                time.sleep(.01)

        if self.__interrupt:
            delta_a_done = steps_done['A']*dir_a
            delta_b_done = steps_done['B']*dir_b

            delta_x_done = (delta_b_done + delta_a_done)//2
            delta_y_done = (delta_b_done - delta_a_done)//2

            self.__pos[0] += delta_x_done
            self.__pos[1] += delta_y_done

        else:
            self.__pos[0] = self.__X_range[x > 0]
            self.__pos[1] = self.__Y_range[y > 0]
    
    def __set_magnet_inner(self, state):
        GPIO.output(driver_config.pin_magnet, GPIO.HIGH if state else GPIO.LOW)

    def __set_servo_inner(self, value):
        self.__servo_pwm.ChangeDutyCycle(value)

    def __put_pawn_inner(self):
        self.__set_servo_inner(driver_config.servo_down)
        time.sleep(1.2)
        self.__set_magnet_inner(0)
        time.sleep(.5)
        self.__set_servo_inner(driver_config.servo_up)
        time.sleep(2.4)

    def __take_pawn_inner(self):
        self.__set_servo_inner(driver_config.servo_down)
        time.sleep(1.2)
        self.__set_magnet_inner(1)
        time.sleep(.5)
        self.__set_servo_inner(driver_config.servo_up)
        time.sleep(2.4)

    def __calibrate_inner(self):
        self.__X_range = [-float('inf'), float('inf')]
        # calibrate X max
        self.__speed = driver_config.max_speed
        while not GPIO.input(driver_config.pin_endstop_X_max):
            self.__step_X_forward_inner()
        
        for _ in range(driver_config.steps_per_cm):
            self.__step_X_backward_inner()
            
        self.__speed = driver_config.max_speed/8
        while not GPIO.input(driver_config.pin_endstop_X_max):
            self.__step_X_forward_inner()
         
        # calibrate X min
        X_range = 0
        self.__speed = driver_config.max_speed
        while not GPIO.input(driver_config.pin_endstop_X_min):
            self.__step_X_backward_inner()
            X_range += 1
        
        for _ in range(driver_config.steps_per_cm):
            self.__step_X_forward_inner()
            X_range -= 1
        
        self.__speed = driver_config.max_speed/8
        while not GPIO.input(driver_config.pin_endstop_X_min):
            self.__step_X_backward_inner()
            X_range += 1

        self.__pos[0] = 0
        self.__X_range = [0, X_range]

        self.__Y_range = [-float('inf'), float('inf')]
        # calibrate Y max
        self.__speed = driver_config.max_speed
        while not GPIO.input(driver_config.pin_endstop_Y_max):
            self.__step_Y_forward_inner()

        for _ in range(driver_config.steps_per_cm):
            self.__step_Y_backward_inner()
            
        self.__speed = driver_config.max_speed/8
        while not GPIO.input(driver_config.pin_endstop_Y_max):
            self.__step_Y_forward_inner()

        # calibrate Y min
        Y_range = 0
        self.__speed = driver_config.max_speed
        while not GPIO.input(driver_config.pin_endstop_Y_min):
            self.__step_Y_backward_inner()
            Y_range += 1
        
        for _ in range(driver_config.steps_per_cm):
            self.__step_Y_forward_inner()
            Y_range -= 1
            
        self.__speed = driver_config.max_speed/8
        while not GPIO.input(driver_config.pin_endstop_Y_min):
            self.__step_Y_backward_inner()
            Y_range += 1

        self.__pos[1] = 0
        self.__Y_range = [0, Y_range]

        self.__speed = driver_config.max_speed
        
        self.__calibrated = True

    def __move_pawn_from_square_to_square_inner(self, from_col, from_row, to_col, to_row):
        self.__set_servo_inner(driver_config.servo_up)
        self.__move_to_square_inner(from_col, from_row)
        self.__take_pawn_inner()
        self.__move_to_square_inner(to_col, to_row)
        self.__put_pawn_inner()
        self.__set_servo_inner(driver_config.servo_up)
    
    def __move_pawn_from_square_to_pos_inner(self, from_col, from_row, to_x, to_y):
        self.__set_servo_inner(driver_config.servo_up)
        self.__move_to_square_inner(from_col, from_row)
        self.__take_pawn_inner()
        self.__move_to_pos_inner(to_x, to_y)
        self.__put_pawn_inner()
        self.__set_servo_inner(driver_config.servo_up)
    
    def __move_pawn_from_pos_to_square_inner(self, from_x, from_y, to_col, to_row):
        self.__set_servo_inner(driver_config.servo_up)
        self.__move_to_pos_inner(from_x, from_y)
        self.__take_pawn_inner()
        self.__move_to_square_inner(to_col, to_row)
        self.__put_pawn_inner()
        self.__set_servo_inner(driver_config.servo_up)
    
    def __move_pawn_from_pos_to_pos_inner(self, from_x, from_y, to_x, to_y):
        self.__set_servo_inner(driver_config.servo_up)
        self.__move_to_pos_inner(from_x, from_y)
        self.__take_pawn_inner()
        self.__move_to_pos_inner(to_x, to_y)
        self.__put_pawn_inner()
        self.__set_servo_inner(driver_config.servo_up)

    def __log(self, log):
        with open('logs/movement_handler.txt', 'a') as log_file:
            log = log.replace('\n', '\n  ')
            log_file.write(f'{datetime.datetime.now().strftime("%d_%m_%Y_%H_%M_%S")} {log}\n')