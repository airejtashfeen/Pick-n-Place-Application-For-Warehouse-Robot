"""Integrated robot controller with navigation and pick-and-place with slot management."""
from controller import Supervisor
import math
import requests
import time
from datetime import datetime, timezone


# Create the Supervisor instance (inherits from Robot).
robot = Supervisor()
TIME_STEP = 32
ROTATING_SPEED = 8.0
SPEED = 5.0

BASE_URL = "http://localhost:4000"

response = requests.get(f"{BASE_URL}/warehouse/get-shelves")
shelves_json = response.json()

shelves = {}  # final dictionary
available_robots = []
orders = []
waypoints = []

# ✅ Module-level variables - DO NOT use 'global' keyword here
BATTERY = 0
CAN_QUANTITY = 0
CURRENT_JOB_ID = 0
JOB_IN_PROGRESS = False

try:
    if shelves_json["success"] and len(shelves_json["data"]) > 0:
        for shelf in shelves_json["data"]:
            name = shelf["name"]
            slots = shelf["slots"]

            shelves[name] = {
                "slots": slots
            }

except Exception as e:
    print("Error fetching shelves :", e)
    
robotId = robot.getName()
battery_response = requests.get(f"{BASE_URL}/warehouse/get-battery-level/{robotId}")
battery_json = battery_response.json()

try : 
    if battery_json["success"] :
        BATTERY = battery_json["data"]
        print(f"✓ Battery level initialized: {BATTERY}%")
        
except Exception as e:
    print("Error fetching Battery :", e)
    

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

def get_available_slots():
    """Get list of available slot IDs"""
    available = []
    for slot in shelves["can_shelf"]["slots"]:
        if slot["available"]:
            available.append(slot["id"])
    return available

def mark_slot_unavailable(slot_id):
    """Mark a slot as unavailable after picking"""
    # API call to make the slot unavailable in database
    payload = {
     "shelfName" : "can_shelf",
     "slotId" : slot_id,
     "status" : False
    }
    slot_response = requests.patch(f"{BASE_URL}/warehouse/update-slot-availability",json = payload) 
    slot_json = slot_response.json()
    try:
        if(slot_json.get("success")):
            for slot in shelves["can_shelf"]["slots"]:
                if slot["id"] == slot_id:
                    slot["available"] = False
                    print(f"✓ Slot {slot_id} marked as unavailable")
                    return True
    except Exception as e:
        print("Error updating slot availability in database", e)
        
    return False
    
def addRobotLog(jobId , batteryPercentage , status , x , y , message):
    robot_id = robot.getName()

    payload = {
    "robotId" : robot_id,
    "jobId" : jobId,
    "batteryPercentage" : batteryPercentage,
    "status": status,
    "position": {
      "x" : round(x,2),
      "y" : round(y,2)
    },
    "message" : message
    }
    
    try:
        response = requests.post(f"{BASE_URL}/warehouse/add-robot-log",json=payload)
        response_json = response.json()
        if response_json["success"]:
            print(response_json["message"])
    except Exception as e:
        print("❌ Error adding robot log",e)
        
        
def pick_can_from_slot(slot_id):
    """
    Execute pick and place sequence for specified slot.
    slot_id: 1, 2, 3, or 4
    """
    # Stop the robot during pick and place
    stop()
    
    # Reset all positions first
    print("🔄 Resetting all arm joints and fingers...")
    for m in arms + fingers:
        try:
            m.setPosition(0.0)
        except Exception as e:
            print(f"⚠️ Could not reset a motor: {e}")
    wait(2.0)
    
    # Configuration based on slot
    if slot_id == 2:
        print(f"\n🥫 === PICKING UP CAN FROM SLOT {slot_id} (down shelf) ===")
        gripper_open = 0.025
        
        # Arm positions during lowering
        arm2_lower = -0.80
        arm3_during_lower = 0
        arm4_during_lower = -0.82
        arm4_final = -1.72
        
        # Drop positions
        arm1_rotate = -2.94
        arm2_drop = -0.52
        arm3_drop = -0.84
        
        # Gripper settings
        gripper_release = 0.02
        release_wait = 2.0
        
        # Open gripper first
        print("\n🟢 Opening gripper before movement...")
        for f in fingers:
            f.setPosition(gripper_open)
        wait(2.0)
        
        # Lowering the arm in stages
        print("\n⬇️ Lowering the arm in stages...")
        print(" → Moving arm2 (lowering part 1)")
        arms[1].setPosition(arm2_lower)
        wait(1.5)
        print(" → Extending arm3 slightly for extra reach")
        arms[2].setPosition(arm3_during_lower)
        wait(2.5)
        print(" → Extending arm4 slightly for extra reach")
        arms[3].setPosition(arm4_during_lower)
        
        print(" → Extending arm4 to final lowered position")
        arms[3].setPosition(arm4_final)
        wait(2.5)
        
    elif slot_id == 4:
        print(f"\n🥫 === PICKING UP CAN FROM SLOT {slot_id} (upper shelf) ===")
        gripper_open = 0.025
        
        # Arm positions during lowering
        arm4_initial = 1.45
        arm2_lower = -0.92
        arm3_during_lower = -1.3
        arm4_during_lower = -0.30
        arm4_final = -1.32
        
        # Drop positions
        arm1_rotate = -2.94
        arm2_drop = -0.32
        arm3_drop = None
        
        # Gripper settings
        gripper_release = 0.02
        release_wait = 2.0
        
        # Open gripper first
        print("\n🟢 Opening gripper before movement...")
        for f in fingers:
            f.setPosition(gripper_open)
        wait(2.0)
        
        # Lowering the arm in stages
        print("\n⬇️ Lowering the arm in stages...")
        print(" → Extending arm4 initial for extra reach")
        arms[3].setPosition(arm4_initial)
        wait(2.5)
        print(" → Extending arm3 slightly for extra reach")
        arms[2].setPosition(-1.15)
        wait(2.5)
        print(" → Moving arm2 (lowering part 1)")
        arms[1].setPosition(arm2_lower)
        wait(1.5)
        print(" → Extending arm4 during lower for extra reach")
        arms[3].setPosition(arm4_during_lower)
        print(" → Extending arm4 to final lowered position")
        arms[3].setPosition(arm4_final)
        wait(2.5)
        
    elif slot_id == 1:
        # Leave space for slot 1 logic
        print(f"\n🥫 === PICKING UP CAN FROM SLOT {slot_id} ===")
        print("⚠️ Slot 1 logic not implemented yet")
        return
        
    elif slot_id == 3:
        # Leave space for slot 3 logic
        print(f"\n🥫 === PICKING UP CAN FROM SLOT {slot_id} ===")
        print("⚠️ Slot 3 logic not implemented yet")
        return
        
    else:
        print(f"❌ Invalid slot ID: {slot_id}")
        return
    
    # Close the gripper
    print("\n✊ Closing gripper (picking up object)...")
    for f in fingers:
        f.setPosition(0.0)
    wait(2.5)
    
    # Lift and rotate arm
    print("\n⬆️ Raising arm2 back up...")
    arms[1].setPosition(0.75)
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
    
    print(f"\n✅ Pick and place sequence complete for slot {slot_id}!")

def pick_can_quantity(quantity,x,y):
    """
    Pick multiple cans based on quantity.
    Only picks from available slots.
    """
    if not isinstance(quantity, int) or quantity <= 0:
        print("❌ Invalid quantity for pick_can (must be positive integer).")
        return

    print(f"\n🟦 Starting pick_can sequence for {quantity} can(s).")
    addRobotLog(CURRENT_JOB_ID,BATTERY,"Working", x , y ,"Starting pick can sequence")
    # Get available slots
    available_slots = get_available_slots()
    print(f"📋 Available slots: {available_slots}")
    
    if len(available_slots) < quantity:
        print(f"⚠️ Warning: Only {len(available_slots)} slots available, but {quantity} requested.")
        quantity = len(available_slots)
    
    # Pick cans from available slots
    for i in range(quantity):
        if i < len(available_slots):
            slot_id = available_slots[i]
            print(f"\n🔹 Picking can #{i+1} from slot {slot_id}.")
            pick_can_from_slot(slot_id)
            mark_slot_unavailable(slot_id)
        else:
            print(f"⚠️ No more available slots for can #{i+1}")
            break
    print(f"\n✅ Completed pick_can for {quantity} can(s).")
    addRobotLog(CURRENT_JOB_ID,BATTERY,"Working", x , y ,"Completed picking can operation")


def updateJobTime(isStartTime,time,jobId):
    payload = {
    "isStartTime" : isStartTime,
    "time" : time,
    "jobId" : jobId
    }
    
    try:
        response = requests.patch(f"{BASE_URL}/warehouse/update-job-time", json=payload)
        response_json = response.json()
        
        if response_json["success"]:
            print("Job time updated successfully!")
      
            
    except Exception as e:
        print("❌ Error updating job time:", e)
    
    

                
def check_allocated_job():
    # ✅ Declare ALL global variables that will be modified
    global CURRENT_JOB_ID, CAN_QUANTITY, JOB_IN_PROGRESS, waypoints, BATTERY
    
    robot_name = robot.getName()
    try:
        response = requests.get(f"{BASE_URL}/warehouse/get-assigned-job/{robot_name}")
        response_json = response.json()
        print("📡 Job check response:", response_json)
        
        if response_json["success"] and len(response_json["data"]) > 0:
            dt = datetime.now(timezone.utc)
            timestamp = dt.isoformat()
            CURRENT_JOB_ID = response_json["data"]["_id"]
            print(f"✓ Job ID assigned: {CURRENT_JOB_ID}")
            
            job_items = response_json["data"]["items"]
            if len(job_items) == 1 and job_items[0]["name"] == "Can":
                CAN_QUANTITY = job_items[0]["quantity"]
                print(f"✓ CAN Quantity in job: {CAN_QUANTITY}")
                addRobotLog(CURRENT_JOB_ID,BATTERY,"Working",2.96,-3.06,f"Starting Job to Pick {CAN_QUANTITY} Cans")
                updateJobTime(True,timestamp,CURRENT_JOB_ID)
                # ✅ Build waypoints with the correct quantity
                new_waypoints = [
                    (1.68, -3.06, 'backward'),
                    ("turn_right", 11.0), 
                    (1.93, -0.59, 'forward'),
                    ("pick_can", CAN_QUANTITY),  # ✅ Uses current CAN_QUANTITY
                    (1.83, -3.20, 'backward'),
                    ("turn_left", 3.0),
                    (0, 0, 1, 0, 'rotation'),
                    (0.70, -3.06, 'backward'), 
                    (3.019, -3.06, 'forward'),
                ]
                
                JOB_IN_PROGRESS = True
                waypoints[:] = new_waypoints
                print(f"✓ Waypoints updated with quantity: {CAN_QUANTITY}")
                print(f"✓ Job status: IN PROGRESS")
        else:
            print("ℹ️ No jobs assigned yet")
            
    except Exception as e:
        print("❌ Error checking allocated job:", e)


def update_job_status(status, jobId):
    # ✅ Declare global variable
    global CURRENT_JOB_ID
    
    payload = {
        "status": status,
        "jobId": jobId
    }
    try:
        response = requests.patch(f"{BASE_URL}/warehouse/update-job-status", json=payload)
        response_json = response.json()
        
        if response_json["success"]:
            print(f"✓ {response_json['message']}")
            print(f"✓ JOB ID COMPLETED: {CURRENT_JOB_ID}")
            CURRENT_JOB_ID = 0  # ✅ Now properly resets the global variable
            
    except Exception as e:
        print("❌ Error updating job status:", e)


def update_robot_availability(status):
    robot_id = robot.getName()
    payload = {
        "status": status,
        "robotId": robot_id
    }
    try:
        response = requests.patch(f"{BASE_URL}/warehouse/update-robot-availability", json=payload)
        response_json = response.json()
        
        if response_json["success"]:
            print(f"✓ {response_json['message']}")
        
    except Exception as e:
        print("❌ Error updating robot availability:", e)


def update_robot_battery(battery_count):
    # ✅ Declare global variable
    global BATTERY
    
    robot_name = robot.getName()
    
    payload = {
        "batteryCount": battery_count,
        "robotId": robot_name
    }
    try:
        response = requests.patch(f"{BASE_URL}/warehouse/update-battery-level", json=payload)
        response_json = response.json()
        
        if response_json["success"]:
            print(f"✓ {response_json['message']}")
            print(f"✓ Battery updated: {BATTERY}%")
            
    except Exception as e:
        print("❌ Error updating battery level:", e)


# Initialize timing variable OUTSIDE the loop
last_call = time.time()

while robot.step(TIME_STEP) != -1:
    
    now = time.time()
    
    # ✅ Check if 15 seconds have passed AND robot is NOT currently working on a job
    if now - last_call >= 10 and not JOB_IN_PROGRESS:
        print("\n⏰ 10 seconds elapsed - Checking Available Jobs...")
        
        # Call check_allocated_job
        check_allocated_job()
      
        # Update last_call time
        last_call = now
           
        
    # Get current position
    pos = gps.getValues()
    current_x = pos[0]
    current_y = pos[1] 
    
    if len(waypoints) > 0:
        # If finished all waypoints, stop
        if current_waypoint_index >= len(waypoints):
            stop()
            print(f"✓ Final Position: ({current_x:.2f},{current_y:.2f})")
            
            # API Call to update job status
            if CURRENT_JOB_ID != 0:  # ✅ Only update if there's a valid job
                print(f"📤 JOB ID SENDING TO API: {CURRENT_JOB_ID}")
                dt = datetime.now(timezone.utc)
                timestamp = dt.isoformat()
                updateJobTime(False,timestamp,CURRENT_JOB_ID)
                addRobotLog(CURRENT_JOB_ID,BATTERY,"Free",current_x,current_y,"Completed job!")
                update_job_status("completed", CURRENT_JOB_ID)
                update_robot_availability("idle")
                
                
            
                BATTERY -= 5
                update_robot_battery(5)
            
            # Reset for next job
            waypoints[:] = []
            current_waypoint_index = 0
            JOB_IN_PROGRESS = False
            print("✓ Robot ready for next job")
            continue
            
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
        
        # Handle pick can command
        if isinstance(current_waypoint, tuple) and len(current_waypoint) >= 2 and current_waypoint[0] == "pick_can":
            quantity = current_waypoint[1]
            print(f"\n🎯 Executing pick_can with quantity = {quantity}")
            addRobotLog(CURRENT_JOB_ID,BATTERY,"Working", current_x , current_y ,"Beginning to pick can")
            pick_can_quantity(quantity,current_x,current_y)
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
                addRobotLog(CURRENT_JOB_ID,BATTERY,"Working", current_x , current_y ,"Reached Waypoint")
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
            print(f"❌ Invalid or unrecognized waypoint format at index {current_waypoint_index}: {current_waypoint}")
            current_waypoint_index += 1 
            
        print(f"Pos: ({current_x:.2f},{current_y:.2f})")