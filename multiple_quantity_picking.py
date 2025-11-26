"""Integrated robot controller with navigation and pick-and-place (Option A: same location for multiple cans)."""
from controller import Supervisor
import math

# Create the Supervisor instance (inherits from Robot).
robot = Supervisor()
TIME_STEP = 32
ROTATING_SPEED = 8.0
SPEED = 5.0

# Get sensors
gps = robot.getDevice("gps")
gps.enable(TIME_STEP)

# Get motors (wheels)
wheel_names = ["wheel1", "wheel2", "wheel3", "wheel4"]
wheels = []
for name in wheel_names:
    m = robot.getDevice(name)
    m.setPosition(float('inf'))  # infinite rotation (velocity mode)
    m.setVelocity(0)
    wheels.append(m)

# Get arm and finger motors
arms = [robot.getDevice(f"arm{i+1}") for i in range(5)]
fingers = [
    robot.getDevice("finger::left"),
    robot.getDevice("finger::right")
]

# Control variables
current_waypoint_index = 0
rotation_start_time = None
is_rotating = False
rotation_direction = None  # 'left' or 'right'
current_rotation_duration = 0

def wait(seconds):
    """Wait for specified seconds while stepping the simulation"""
    start = robot.getTime()
    while robot.step(TIME_STEP) != -1:
        if robot.getTime() - start > seconds:
            break
    
def rotate_left(speed=1.0):
    wheels[0].setVelocity(-speed)
    wheels[1].setVelocity(speed)
    wheels[2].setVelocity(speed)
    wheels[3].setVelocity(-speed)

def rotate_right(speed=1.0):
    wheels[0].setVelocity(speed)
    wheels[1].setVelocity(-speed)
    wheels[2].setVelocity(-speed)
    wheels[3].setVelocity(speed)
    
def drive_forward(speed):
    for w in wheels:
        w.setVelocity(speed)
        
def drive_backward(speed):
    for w in wheels:
        w.setVelocity(-speed)
        
def stop():
    for w in wheels:
        w.setVelocity(0)

def calculate_distance(pos1, pos2):
    """Calculate Euclidean distance between two positions"""
    return math.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)

def get_robot_node():
    """Get the robot's node to access translation and rotation fields"""
    return robot.getSelf()

def set_robot_rotation(x, y, z, angle):
    """Set the robot's rotation directly"""
    robot_node = get_robot_node()
    if robot_node is not None:
        rotation_field = robot_node.getField("rotation")
        if rotation_field is not None:
            rotation_field.setSFRotation([x, y, z, angle])
            print(f"🔄 Robot rotation set to: axis=({x}, {y}, {z}), angle={angle:.2f} rad")
            return True
    print("❌ Failed to set rotation - robot node or rotation field not accessible")
    return False

def pick_and_place(target_object):
    """
    Execute pick and place sequence for specified object.
    target_object: "BISCUIT", "CAN", or "CEREAL"
    """
    # Stop the robot during pick and place
    stop()
    
    # Reset all positions first
    print("🔄 Resetting all arm joints and fingers...")
    for m in arms + fingers:
        try:
            m.setPosition(0.0)
        except Exception as e:
            # Safety: some motors might not accept setPosition in certain states
            print(f"⚠️ Could not reset a motor: {e}")
    wait(2.0)
    
    # Configuration based on target
    if target_object == "BISCUIT":
        print("\n📦 === PICKING UP BISCUIT BOX (down shelf) ===")
        gripper_open = 0.025
        # arms[0].setPosition(0.37)
        # Arm positions during lowering - ADJUSTED FOR NEW POSITION
        arm2_lower = -0.80  # Increased reach (was -0.58)
        arm3_during_lower = 0
        arm4_during_lower = -0.82  # Increased reach (was -1.78)
        arm4_final = -1.72
        
        # Drop positions
        arm1_rotate = -2.94
        arm2_drop = -0.52  # Slightly adjusted (was -1.03)
        arm3_drop = -0.84
        
        # Gripper settings
        gripper_release = 0.02
        release_wait = 2.0
        
    elif target_object == "CAN":
        print("\n🥫 === PICKING UP CAN (upper shelf) ===")
        gripper_open = 0.025
        
        # Arm positions during lowering - ADJUSTED FOR NEW POSITION
        arm4_initial = 1.45  # Increased reach (was 1.4)
        arm2_lower = -0.92  # Increased reach (was -1.13)
        arm3_during_lower = -1.3 # Increased reach (was -0.52)
        arm4_during_lower = -0.30 # Increased reach (was -1.72)
        arm4_final = -1.32 # Increased reach (was -1.72)
        
        # Drop positions
        arm1_rotate = -2.94
        arm2_drop = -0.32  # Slightly adjusted (was -1.03)
        arm3_drop = None
        
        # Gripper settings
        gripper_release = 0.02
        release_wait = 2.0
        
    elif target_object == "CEREAL":
        print("\n🥣 === PICKING UP CEREAL BOX ===")
        gripper_open = 0.025
        
        # Arm positions during lowering - ADJUSTED FOR NEW POSITION
        arm4_initial = 1.45  # Increased reach (was 1.4)
        arm2_lower = -1.63  # Increased reach (was -1.58)
        arm3_during_lower = -1.83  # Increased reach (was -1.78)
        arm4_during_lower = None
        arm4_final = -1.70  # Increased reach (was -1.65)
        
        # Drop positions
        arm1_rotate = -3.04
        arm2_drop = -0.08  # Adjusted (was -0.03)
        arm3_drop = None
        
        # Gripper settings
        gripper_release = 0.025
        release_wait = 3.0
        
    else:
        print(f"❌ Invalid target object: {target_object}")
        return
    
    # Open gripper first
    print("\n🟢 Opening gripper before movement...")
    for f in fingers:
        f.setPosition(gripper_open)
    wait(2.0)
    
    # Lowering the arm in stages
    print("\n⬇️ Lowering the arm in stages...")
    
    if target_object == "BISCUIT":
        print(" → Moving arm2 (lowering part 1)")
        arms[1].setPosition(arm2_lower)
        wait(1.5)  # Slightly longer wait for stability
        print(" → Extending arm3 slightly for extra reach")
        arms[2].setPosition(arm3_during_lower)
        wait(2.5)  # Longer wait for extended reach
        print(" → Extending arm4 slightly for extra reach")
        arms[3].setPosition(arm4_during_lower)
        
        print(" → Extending arm4 to final lowered position")
        arms[3].setPosition(arm4_final)
        wait(2.5)  # Longer wait for extended reach
        
    else:  # CAN or CEREAL
        # Use local vars but guard against None if some values not set
        if 'arm4_initial' in locals():
            print(" → Extending arm4 initial for extra reach")
            arms[3].setPosition(arm4_initial)
            wait(2.5)
        else:
            print(" → arm4_initial not defined for this object")
        print(" → Extending arm3 slightly for extra reach")
        try:
            arms[2].setPosition(-1.15)
        except Exception:
            # fallback to previously set variable if exists
            try:
                arms[2].setPosition(arm3_during_lower)
            except Exception:
                pass
        wait(2.5)
        print(" → Moving arm2 (lowering part 1)")
        arms[1].setPosition(arm2_lower)
        wait(1.5)

        if 'arm4_during_lower' in locals() and arm4_during_lower is not None:
            print(" → Extending arm4 during lower for extra reach")
            arms[3].setPosition(arm4_during_lower)
        if 'arm4_final' in locals():
            print(" → Extending arm4 to final lowered position")
            arms[3].setPosition(arm4_final)
        wait(2.5)  # Longer wait for extended reach
    
    # Close the gripper
    print("\n✊ Closing gripper (picking up object)...")
    for f in fingers:
        f.setPosition(0.0)
    wait(2.5)  # Longer wait to ensure grip
    
    # Lift and rotate arm
    print("\n⬆️ Raising arm2 back up...")
    arms[1].setPosition(0.75)  # Slightly higher lift
    wait(2.0)
    
    print("\n🔁 Rotating arm1 (turning around)...")
    arms[0].setPosition(arm1_rotate)
    wait(2.0)
    
    # Lower to drop position
    print("\n⬇️ Lowering arm2 slightly...")
    arms[1].setPosition(arm2_drop)
    wait(2.0)
    
    if 'arm3_drop' in locals() and arm3_drop is not None:
        print("\n⬇️ Lowering arm3 slightly...")
        arms[2].setPosition(arm3_drop)
        wait(2.0)
    
    # Open gripper to drop object
    print("\n👐 Opening gripper to release object...")
    for f in fingers:
        f.setPosition(gripper_release)
    wait(release_wait)
    
    # Return arm to neutral position
    print("\n⬆️ Lifting arm2 again...")
    arms[1].setPosition(0.90)
    wait(2.0)
    
    print("\n🔁 Returning arm1 to front position...")
    arms[0].setPosition(0.0)
    wait(2.0)
    
    print("\n🔄 Resetting arm3 to starting position...")
    arms[2].setPosition(0.0)
    wait(2.0)
    
    print("\n🔄 Resetting arm4 to starting position...")
    arms[3].setPosition(0.0)
    wait(2.0)
    
    print("\n🔄 Resetting arm2 to starting position...")
    arms[1].setPosition(0.0)
    wait(2.0)
    
    print("\n🟢 Opening gripper (final state)...")
    for f in fingers:
        f.setPosition(0.02)
    wait(2.0)
    
    print("\n✅ Pick and place sequence complete!")

def pick_can_quantity(quantity):
    """
    Pick multiple cans based on quantity (Option A: all cans reachable from same spot).
    - First can uses BISCUIT logic (down shelf)
    - Remaining cans use CAN logic (upper shelf)
    """
    if not isinstance(quantity, int) or quantity <= 0:
        print("❌ Invalid quantity for pick_can (must be positive integer).")
        return

    print(f"\n🟦 Starting pick_can sequence for {quantity} can(s).")

    # First can: use BISCUIT picking routine (down shelf)
    print("\n🔹 Picking can #1 using BISCUIT routine (down shelf).")
    pick_and_place("BISCUIT")

    # Remaining cans: use CAN picking routine
    for i in range(2, quantity + 1):
        print(f"\n🔸 Picking can #{i} using CAN routine (upper shelf).")
        pick_and_place("CAN")

    print(f"\n✅ Completed pick_can for {quantity} can(s).")

# Enhanced Waypoints format:
# For movement: (target_x, target_y, movement_type)
# For turning: ("turn_left", duration_in_seconds) or ("turn_right", duration_in_seconds)
# For direct rotation: (x, y, z, angle, 'rotation') - sets robot orientation directly
# For picking: ("pick_can", quantity) or ("pick_biscuit",) or ("pick_cereal",)

waypoints = [
    (1.68, -3.06, 'backward'),
    ("turn_right", 11.0), 
    (1.93, -0.59, 'forward'),
    ("pick_can", 2),            # example: pick 2 cans at same place (1st uses BISCUIT, 2nd uses CAN)
    (1.83, -3.20, 'backward'),
    ("turn_left", 3.0),
    # (0, 0, 1, 3.14 , 'rotation'), 
    (0, 0, 1, 0 , 'rotation'),
    (0.70, -3.06, 'backward'), 
    (3.019, -3.06, 'forward'),
    # (0, 0, 1, 0 , 'rotation'),
]

while robot.step(TIME_STEP) != -1:
    # Get current position
    pos = gps.getValues()
    current_x = pos[0]
    current_y = pos[1] 
    
    # If finished all waypoints, stop
    if current_waypoint_index >= len(waypoints):
        stop()
        print(f"Final Position: ({current_x:.2f},{current_y:.2f})")
        print("🎉 All waypoints reached!")
        break
        
    current_waypoint = waypoints[current_waypoint_index]
    
    # Check if we're currently rotating
    if is_rotating:
        current_time = robot.getTime()
        rotation_elapsed = current_time - rotation_start_time
        
        # Check if rotation duration has completed
        if rotation_elapsed >= current_rotation_duration:
            print(f"Pos: ({current_x:.2f},{current_y:.2f})")
            print(f"⏰ {rotation_direction.title()} rotation completed after {rotation_elapsed:.1f} seconds")
            stop()
            is_rotating = False
            rotation_start_time = None
            current_waypoint_index += 1
            continue
        else:
            # Continue rotating in the same direction
            if rotation_direction == 'left':
                rotate_left(ROTATING_SPEED)
            elif rotation_direction == 'right':
                rotate_right(ROTATING_SPEED)
            print(f"🔄 Rotating {rotation_direction}... {rotation_elapsed:.1f}s / {current_rotation_duration:.1f}s")
            continue
    
    # Handle pick and place commands (now support tuples like ("pick_can", qty))
    # 1) tuple with pick command + quantity e.g. ("pick_can", 2)
    if isinstance(current_waypoint, tuple) and len(current_waypoint) >= 1 and isinstance(current_waypoint[0], str):
        command = current_waypoint[0]

        # Multi-can pick handling: ("pick_can", quantity)
        if command == "pick_can":
            # Validate quantity presence
            if len(current_waypoint) >= 2:
                quantity = current_waypoint[1]
                print(f"\n🎯 Executing pick_can with quantity = {quantity}")
                pick_can_quantity(quantity)
            else:
                print("❌ pick_can waypoint missing quantity. Use ('pick_can', quantity).")
            current_waypoint_index += 1
            continue

        # Single-object pick as tuple like ("pick_biscuit",) or ("pick_biscuit", 1) - ignore extra numbers
        if command.startswith("pick_"):
            object_type = command.replace("pick_", "").upper()
            print(f"\n🎯 Executing pick_and_place for {object_type}...")
            pick_and_place(object_type)
            current_waypoint_index += 1
            continue

    # Handle direct rotation waypoints: (x, y, z, angle, 'rotation')
    if isinstance(current_waypoint, tuple) and len(current_waypoint) == 5 and current_waypoint[4] == 'rotation':
        rot_x, rot_y, rot_z, rot_angle, _ = current_waypoint
        print(f"🎯 Setting robot rotation to axis=({rot_x}, {rot_y}, {rot_z}), angle={rot_angle:.2f} rad")
        stop()
        success = set_robot_rotation(rot_x, rot_y, rot_z, rot_angle)
        if success:
            print(f"✓ Rotation waypoint {current_waypoint_index + 1} completed")
        else:
            print(f"⚠️ Rotation waypoint {current_waypoint_index + 1} failed")
        current_waypoint_index += 1
        continue
            
    # Movement waypoint: (x, y, movement_type)
    if isinstance(current_waypoint, tuple) and len(current_waypoint) == 3:
        target_x, target_y, movement_type = current_waypoint
        # Check if target is reached
        distance = calculate_distance((current_x, current_y), (target_x, target_y))
        
        if distance < 0.1:  # 10cm tolerance
            print(f"✓ Reached waypoint {current_waypoint_index + 1}: ({target_x:.2f}, {target_y:.2f})")
            print(f"  Final position: ({current_x:.2f}, {current_y:.2f})")
            current_waypoint_index += 1
            stop()
            continue
        
        # Movement logic based on relative position
        if movement_type == 'forward':
            drive_forward(SPEED)
        elif movement_type == 'backward':
            drive_backward(SPEED)
        else:
            # Unknown movement type -> stop and move on
            print(f"⚠️ Unknown movement type '{movement_type}' at waypoint {current_waypoint_index + 1}. Stopping.")
            stop()
            current_waypoint_index += 1
            continue
            
    # Turn command: ("turn_direction", duration_in_seconds)
    elif isinstance(current_waypoint, tuple) and len(current_waypoint) == 2 and isinstance(current_waypoint[0], str) and current_waypoint[0].startswith("turn_"):
        turn_command, duration = current_waypoint
        print(f"🔄 Starting {turn_command} rotation for {duration:.1f} seconds...")
        
        if turn_command == 'turn_left':
            rotate_left(ROTATING_SPEED)
            rotation_direction = 'left'
        elif turn_command == 'turn_right':
            rotate_right(ROTATING_SPEED)
            rotation_direction = 'right'
            
        is_rotating = True
        rotation_start_time = robot.getTime()
        current_rotation_duration = duration

    else:
        # Fallback invalid waypoint format
        print(f"❌ Invalid or unrecognized waypoint format at index {current_waypoint_index}: {current_waypoint}")
        current_waypoint_index += 1 
        
    print(f"Pos: ({current_x:.2f},{current_y:.2f})")
