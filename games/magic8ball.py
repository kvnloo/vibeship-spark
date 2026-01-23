#!/usr/bin/env python3
"""
Magic 8-Ball CLI - Ask the mystical Spark 8-Ball your questions!

Usage:
    python magic8ball.py                    # Interactive mode
    python magic8ball.py "Your question?"   # Single question
    python magic8ball.py --spark            # Use Spark-themed responses
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path


# ASCII Art for the 8-ball
BALL_ART = r"""
        _.a$$$$$a._
      ,$$$$$$$$$$$$$,
     d$$$$$$$$$$$$$$$b
    d$$$$$$$$~`~$$$$$$b
   ($$$$$$$`     `$$$$$)
   $$$$$$$         $$$$$
   $$$$$$$   {%s}   $$$$$
   $$$$$$$         $$$$$
   ($$$$$$$,     ,$$$$$)
    $$$$$$$$a]_[a$$$$$$$
     Y$$$$$$$$$$$$$$$Y
      `$$$$$$$$$$$$$`
        `~$$$$$$$~`
"""

BALL_SIMPLE = r"""
    .--------.
   /          \
  |    {%s}    |
   \          /
    '--------'
"""


def load_responses(responses_file: Path) -> dict:
    """Load responses from JSON file."""
    if not responses_file.exists():
        raise FileNotFoundError(f"Responses file not found: {responses_file}")

    with open(responses_file, 'r') as f:
        return json.load(f)


def get_response(responses: dict, spark_mode: bool = False) -> str:
    """Get a random response."""
    # Decide which category
    if spark_mode and random.random() < 0.4:
        # 40% chance of Spark special response
        category = "spark_special"
    else:
        # Weighted: 50% positive, 25% neutral, 25% negative
        roll = random.random()
        if roll < 0.5:
            category = "positive"
        elif roll < 0.75:
            category = "neutral"
        else:
            category = "negative"

    return random.choice(responses.get(category, ["The spirits are silent."]))


def shake_animation(duration: float = 1.5):
    """Display a shaking animation."""
    frames = [
        "  Shaking",
        "   Shaking.",
        "    Shaking..",
        "     Shaking...",
        "    Shaking..",
        "   Shaking.",
    ]

    end_time = time.time() + duration
    frame_idx = 0

    while time.time() < end_time:
        sys.stdout.write(f"\r{frames[frame_idx % len(frames)]}   ")
        sys.stdout.flush()
        time.sleep(0.15)
        frame_idx += 1

    sys.stdout.write("\r" + " " * 30 + "\r")
    sys.stdout.flush()


def display_response(response: str, fancy: bool = True):
    """Display the response with optional ASCII art."""
    if fancy:
        # Truncate response to fit in ball
        short = response[:15] + "..." if len(response) > 18 else response
        # Center it
        padded = short.center(10)
        print(BALL_SIMPLE.replace("{%s}", padded[:10]))

    print(f"\n  The Magic 8-Ball says:\n")
    print(f"    \"{response}\"\n")


def interactive_mode(responses: dict, spark_mode: bool = False):
    """Run interactive question-answer loop."""
    print("\n" + "=" * 50)
    print("       MAGIC 8-BALL")
    if spark_mode:
        print("     (Spark Edition)")
    print("=" * 50)
    print("\n  Ask your yes/no questions!")
    print("  Type 'quit' or 'exit' to leave.\n")

    while True:
        try:
            question = input("  Your question: ").strip()

            if not question:
                print("  (Please ask a question)\n")
                continue

            if question.lower() in ('quit', 'exit', 'q'):
                print("\n  The 8-Ball fades into the mist...\n")
                break

            if '?' not in question:
                print("  (That doesn't look like a question. Try adding a '?')\n")
                continue

            # Shake and reveal
            shake_animation()
            response = get_response(responses, spark_mode)
            display_response(response)

        except KeyboardInterrupt:
            print("\n\n  The 8-Ball fades into the mist...\n")
            break
        except EOFError:
            break


def single_question(question: str, responses: dict, spark_mode: bool = False):
    """Answer a single question."""
    print(f"\n  Question: \"{question}\"\n")
    shake_animation()
    response = get_response(responses, spark_mode)
    display_response(response)


def main():
    parser = argparse.ArgumentParser(
        description="Magic 8-Ball - Ask your questions!",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python magic8ball.py                     # Interactive mode
    python magic8ball.py "Will it work?"     # Single question
    python magic8ball.py --spark "Will Spark learn this?"
        """
    )

    parser.add_argument("question", nargs="?", help="Question to ask (optional)")
    parser.add_argument("--spark", "-s", action="store_true",
                       help="Enable Spark-themed responses")
    parser.add_argument("--no-animation", action="store_true",
                       help="Skip the shake animation")

    args = parser.parse_args()

    # Find responses file
    script_dir = Path(__file__).parent
    responses_file = script_dir / "8ball_responses.json"

    try:
        responses = load_responses(responses_file)
    except FileNotFoundError as e:
        print(f"\n  Error: {e}")
        print("  Make sure 8ball_responses.json exists in the same directory.\n")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"\n  Error: Invalid JSON in responses file: {e}\n")
        sys.exit(1)

    # Run appropriate mode
    if args.question:
        single_question(args.question, responses, args.spark)
    else:
        interactive_mode(responses, args.spark)


if __name__ == "__main__":
    main()
