"""
Standalone Supervisor Service - Runs independently from simulation
Manages order processing and job dispatching without blocking simulation
"""
import requests
import time
import sys
import os
from datetime import datetime

PROJECT_ROOT = "/Users/abdulbasit/Documents/FYP"
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "utils"))

from utils.algorithm import job_dispatcher, assign_jobs

BASE_URL = "http://localhost:4000"
CHECK_INTERVAL = 15  # seconds

# Service state
available_robots = []
orders = []
is_running = True

def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def process_orders_and_jobs():
    """Fetch orders, dispatch jobs, and assign to robots"""
    global orders, available_robots
    
    try:
        # Fetch pending orders and available robots
        log("📡 Fetching orders and robots...")
        robots_response = requests.get(
            f"{BASE_URL}/warehouse/get-available-robots",
            timeout=5  # Timeout to prevent hanging
        )
        orders_response = requests.get(
            f"{BASE_URL}/warehouse/get-pending-orders",
            timeout=5
        )
        
        orders_json = orders_response.json()
        robots_json = robots_response.json()

        if robots_json["success"] and orders_json["success"]:
            orders = orders_json["data"]
            available_robots = robots_json["data"]
            log(f"✓ Found {len(orders)} pending orders and {len(available_robots)} available robots")
            
            # Process orders and create jobs
            if len(orders) > 0:
                log(f"🔄 Dispatching {len(orders)} orders...")
                job_dispatcher(orders)
                orders = []
            
            # Assign jobs to available robots
            if len(available_robots) > 0:
                assign_jobs(available_robots)
                available_robots = []
        else:
            log("⚠️ API returned unsuccessful response")
            
    except requests.Timeout:
        log("❌ Request timeout - API not responding")
    except requests.ConnectionError:
        log("❌ Connection error - Is the server running?")
    except Exception as e:
        log(f"❌ Error processing orders/robots: {e}")

def main():
    """Main service loop"""
    log("🎯 Supervisor Service Started")
    log(f"📍 Checking orders every {CHECK_INTERVAL} seconds")
    log(f"🌐 API Base URL: {BASE_URL}")
    
    last_check = time.time()
    
    try:
        while is_running:
            current_time = time.time()
            
            # Check if interval has passed
            if current_time - last_check >= CHECK_INTERVAL:
                log("\n" + "="*50)
                process_orders_and_jobs()
                log("="*50)
                last_check = current_time
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        log("\n🛑 Supervisor Service stopped by user")
    except Exception as e:
        log(f"\n❌ Fatal error: {e}")
    finally:
        log("👋 Supervisor Service shut down")

if __name__ == "__main__":
    main()