# =========================================================================================
# Human Agent 
# =========================================================================================
# This file defines a specialized Human agent class that provides a "human-in-the-loop"
# mechanism within the multi-agent environment. While not a core component of the
# reversible multi-agent system described in the primary framework, it serves as
# an optional extension where a human user can interrupt or override the system’s
# backtracking logic at runtime.
#
# Purpose:
#   1. Real-Time Intervention: The Human agent can observe intermediate reasoning
#      steps and decide whether to allow or prevent backtracking.
#   2. Directed Backtrack: If the user deems a particular chain of thought incorrect,
#      they can instruct the system to revert to a specific checkpoint for re-analysis.
#   3. Experimental Feature: This feature is primarily intended for developers or
#      researchers who wish to test and refine the multi-agent pipeline, especially
#      focusing on how well it handles external override or alignment requests.
# =========================================================================================

import sys
from Agent.agent import Agent


class Human(Agent):
    """
    The Human agent enables user interaction in a multi-agent environment:
    1. Monitoring the reasoning flow.
    2. Deciding whether to intervene based on the system’s current step.
    3. Forcing partial or full backtracks to earlier checkpoints if desired.
    4. Overriding backtracking logic at a particular step to test system responses.
    """

    name = "human"

    def __init__(self, name: str = None):
        """
        :param name: If not given, uses the default name "human".
        """
        super().__init__(name=name if name else self.name)

    def decide_intervention(self, step_info: str) -> bool:
        """
        Displays the current reasoning step to the user and awaits a decision.
        The user can type 'y' or 'n' to indicate whether to intervene.

        :param step_info: A textual description of the system’s latest reasoning step.
        :return: True if the user wishes to intervene, False otherwise.
        """
        print("\n[HUMAN] The system performed the following step:\n")
        print(step_info)
        print("\nWould you like to intervene? (y/n): ", end="", flush=True)

        choice = sys.stdin.readline().strip().lower()
        if choice.startswith('y'):
            print("[HUMAN] Intervention chosen.")
            return True
        print("[HUMAN] No intervention.")
        return False

    def request_backtrack(self, max_checkpoint: int) -> int:
        """
        If an intervention is chosen, prompts the user to specify a checkpoint
        to revert to. The user can enter an integer between 0 and max_checkpoint,
        or -1 to cancel backtracking.

        :param max_checkpoint: The highest valid checkpoint index for reversion.
        :return: The chosen checkpoint index, or -1 to skip backtracking.
        """
        if max_checkpoint < 0:
            print("[HUMAN] No valid checkpoints available.")
            return -1

        print(f"[HUMAN] You may choose a checkpoint to revert to (0..{max_checkpoint}).")
        print("Enter -1 to skip backtracking: ", end="", flush=True)

        while True:
            user_input = sys.stdin.readline().strip()
            try:
                checkpoint = int(user_input)
                if (checkpoint == -1) or (0 <= checkpoint <= max_checkpoint):
                    if checkpoint == -1:
                        print("[HUMAN] Skipping backtracking.")
                    else:
                        print(f"[HUMAN] Chosen checkpoint: {checkpoint}")
                    return checkpoint
                else:
                    print(f"[HUMAN] Please enter a number -1 or between 0 and {max_checkpoint}: ", end="", flush=True)
            except ValueError:
                print(f"[HUMAN] Invalid input. Please enter an integer -1..{max_checkpoint}: ", end="", flush=True)

    def override_backtracking(self, current_step: int) -> bool:
        """
        Enables or disables backtracking for the current step. If the user chooses
        to disable backtracking, no agent in the system can revert to an earlier
        state for this step.

        :param current_step: The numeric index of the system’s current reasoning step.
        :return: True if the user forcibly disables backtracking, False otherwise.
        """
        print(f"[HUMAN] You are at reasoning step #{current_step}.")
        print("Do you want to forcibly DISABLE backtracking at this step? (y/n): ", end="", flush=True)

        choice = sys.stdin.readline().strip().lower()
        if choice.startswith('y'):
            print("[HUMAN] Backtracking is disabled at this step by user override.")
            return True
        print("[HUMAN] Backtracking remains enabled.")
        return False

    def receive_message(self, msg):
        """
        Reacts to incoming system messages. A typical usage scenario:
          1. The environment or a supervisory agent sends a message that includes
             'step_info' and 'max_checkpoint' (or similar) if it wants to ask the user
             whether they want to intervene or override backtracking.
          2. This method calls decide_intervention() and possibly request_backtrack()
             or override_backtracking() accordingly.
          3. The results can be returned or inserted into self.local_state for
             further consumption by the environment.

        :param msg: A dictionary with possible keys like 'step_info' and 'max_checkpoint'.
        """
        step_info = msg.get("step_info", "")
        max_cp = msg.get("max_checkpoint", -1)
        current_step = msg.get("current_step", 0)

        if step_info:
            user_intervene = self.decide_intervention(step_info)
            if user_intervene:
                chosen_cp = self.request_backtrack(max_cp)
                if chosen_cp != -1:
                    # The environment or a higher-level supervisory agent
                    # might use this result to actually apply a system-wide rollback.
                    self.local_state["chosen_checkpoint"] = chosen_cp

            forced_disable = self.override_backtracking(current_step)
            if forced_disable:
                self.local_state["disable_backtrack"] = True
            else:
                self.local_state["disable_backtrack"] = False

