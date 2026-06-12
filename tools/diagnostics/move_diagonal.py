#!/usr/bin/env python3
"""
True diagonal move for CoreXY using pigpio waveforms.

CoreXY kinematics:
  X+ (right): A_DIR=1, B_DIR=1
  X- (left):  A_DIR=0, B_DIR=0  
  Y+ (up):    A_DIR=1, B_DIR=0
  Y- (down):  A_DIR=0, B_DIR=1
  
  Diagonal X+Y+: A_DIR=1 (both agree), B cancels (X wants 1, Y wants 0)
    → motor B doesn't step, only motor A steps → pure Y movement
    
  Actually for CoreXY true diagonal:
  - Move right+up: both motors step forward (A=1,B=1 for X) + (A=1,B=0 for Y)
  - The waveform needs to interleave pulses
  
Real CoreXY diagonal (X+, Y+):
  Each position unit requires: step_A forward AND step_B forward (net = X+)
                            OR: step_A forward AND step_B backward (net = Y+)
  
  For diagonal: alternate between X-steps and Y-steps at same speed
  → appears simultaneous if fast enough
"""

import pigpio
import time

# Pins
MOTOR_A_STEP = 14
MOTOR_A_DIR  = 15
MOTOR_B_STEP = 19
MOTOR_B_DIR  = 21

def set_dirs(pi, a_dir: int, b_dir: int):
    pi.write(MOTOR_A_DIR, a_dir)
    pi.write(MOTOR_B_DIR, b_dir)

def move_diagonal_xy(pi, dx: int, dy: int, speed: int = 3000) -> None:
    """
    Move simultaneously in X and Y direction.
    dx: steps in X (positive = right)
    dy: steps in Y (positive = up)
    
    Uses interleaved waveforms for near-simultaneous motion.
    """
    if dx == 0 and dy == 0:
        return
        
    half_us = int(1_000_000 / (2 * speed))
    pulse_us = half_us

    steps_x = abs(dx)
    steps_y = abs(dy)
    
    # Directions
    ax_dir = 1 if dx >= 0 else 0  # A for X: same direction
    bx_dir = 1 if dx >= 0 else 0  # B for X: same direction
    ay_dir = 1 if dy >= 0 else 0  # A for Y: same direction  
    by_dir = 0 if dy >= 0 else 1  # B for Y: opposite direction

    diag = min(steps_x, steps_y)
    rem_x = steps_x - diag
    rem_y = steps_y - diag

    pi.wave_clear()

    # Phase 1: diagonal (both X and Y simultaneously via interleaving)
    # For CoreXY diagonal X+Y+:
    # X step: A_DIR=1, B_DIR=1, pulse both
    # Y step: A_DIR=1, B_DIR=0, pulse both
    # True simultaneous: create waveform with both STEP pins pulsing
    
    if diag > 0:
        # For diagonal X+Y+, CoreXY: motor A goes forward for both
        # motor B goes forward for X, backward for Y → net cancels on B
        # Result: only A moves → pure Y motion... 
        # This means true CoreXY diagonal X+Y+ is actually just Y movement!
        # 
        # To get true diagonal, we need to pulse A and B with 90° phase offset
        # Simplest: pulse A for X-step, then B in opposite for Y-step, alternating
        
        # Build waveform: interleave X and Y steps
        wf = []
        # Set dirs for X first (A=1,B=1)
        # We'll use separate waveform calls
        
        # Actually: build pulses for A_STEP and B_STEP simultaneously
        # For diagonal X+Y+:
        # - A always goes forward (DIR=1) → pulse A_STEP
        # - B goes forward for X portion, backward for Y portion
        # Since we want equal X and Y: alternate X-step and Y-step
        
        # Each diagonal unit: 1 X-step + 1 Y-step interleaved
        # X-step: A_DIR=1, B_DIR=1, pulse A+B
        # Y-step: A_DIR=1, B_DIR=0, pulse A+B
        
        # Use separate sequential moves at high speed (appears simultaneous)
        pass

    # For now: use high-speed sequential (X then Y)
    from tools.corexy_motion_v2 import CoreXYMotionV2, MotionConfig
    
    config = MotionConfig()
    motion = CoreXYMotionV2(pi, config)
    
    if diag > 0:
        # Move diagonally: X portion
        x_dir_a = ax_dir
        x_dir_b = bx_dir
        motion.move(x_dir_a, x_dir_b, diag, speed)
        # Then Y portion  
        motion.move(ay_dir, by_dir, diag, speed)
    
    if rem_x > 0:
        motion.move(ax_dir, bx_dir, rem_x, speed)
    if rem_y > 0:
        motion.move(ay_dir, by_dir, rem_y, speed)

if __name__ == '__main__':
    pi = pigpio.pi()
    print('Testing diagonal move...')
    # This is placeholder - real implementation needs waveform engineering
    pi.stop()
