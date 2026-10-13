import argparse
from guardian.laptop.agent import LaptopAgent

def main():
    parser = argparse.ArgumentParser(description="Live run LaptopAgent")
    parser.add_argument("--live", action="store_true", help="Enable actual clicking and typing")
    parser.add_argument("--max-steps", type=int, default=6, help="Maximum steps to run")
    parser.add_argument("--task", type=str, default="Open Notepad and type hello", help="Task to execute")
    args = parser.parse_args()

    agent = LaptopAgent(model_name="gemini") # Using gemini backend so it's reliable and fast
    print(f"Starting Run: '{args.task}' (Live={args.live})")
    
    logs = agent.run(args.task, live=args.live, max_steps=args.max_steps)
    
    print("\n--- Final Summary ---")
    import json
    for action in logs:
        print(json.dumps(action, indent=2))
        
    print(f"\nLogs saved to: {agent.run_log_dir}")

if __name__ == "__main__":
    main()
