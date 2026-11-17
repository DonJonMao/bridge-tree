# =========================================================================================
# environment.py
# =========================================================================================
# This file defines the core Environment class for managing multiple agents, orchestrating
# concurrency, maintaining a global message pool, and facilitating partial or holistic 
# backtracking across all agents if needed. It references the paper’s non-monotonic 
# multi-agent architecture, dividing responsibilities into Execution, Supervisory, and 
# Interaction layers, and supports a time-stepped concurrency model.
# =========================================================================================

import time
import copy
from Interaction.messagepool import MessagePool
from Interaction.message import Message

class Environment:
    """
    Environment is the base class that manages a collection of agents and a shared
    message pool, enabling multi-agent interactions and concurrency. It can:
      - Track agent states
      - Schedule time-step executions
      - Initiate or accept conflict/backtracking signals
      - Provide a foundation for specialized sub-environments
    """

    def __init__(self, people: list, args):
        """
        :param people: A list of agents or participants.
        :param args: Configuration parameters (e.g. model settings, temperature, 
                     or concurrency options) relevant to multi-agent reasoning.
        """
        self.people = people
        self.args = args
        self.n = len(self.people)

        # A central message pool for storing and retrieving all conversation messages
        self.message_pool = MessagePool()

        # Maintain a global timeline that increments each "tick" or time-step
        self.current_time = 0

        # For global backtracking, we maintain snapshots of environment state 
        # at discrete time indices.
        self.global_history = {}

        # Maintain a conflict flag that can be raised by any agent or by the environment
        self.global_conflict_raised = False
        self.conflict_details = None

        # Register each agent with references to the environment or message pool if needed
        for agent in self.people:
            agent.message_bus = self  # So they can call `send_message` if we treat Env as a bus
            # Additional environment-level registration logic as needed

    def broadcast_message(self, sender, msg_type, content):
        """
        Broadcasts a message to all participants except the sender. Could be used
        by a Supervisor or Controller agent, or by the environment itself.
        """
        for agent in self.people:
            if agent.name != sender:
                agent.receive_message({
                    "sender": sender,
                    "receiver": "ALL",
                    "msg_type": msg_type,
                    "content": content
                })

    def send_message(self, sender, receiver, msg_type, content):
        """
        Called by agents to relay messages. If 'receiver' is 'ALL', it broadcasts
        to everyone else. Otherwise, it finds the intended agent and passes the message.
        The environment also stores a record in the message pool.
        """
        msg = Message(content=content, send_from=sender, send_to=receiver)
        self.message_pool.update_message(msg)

        if receiver == "ALL":
            self.broadcast_message(sender, msg_type, content)
        else:
            for agent in self.people:
                if agent.name == receiver:
                    agent.receive_message({
                        "sender": sender,
                        "receiver": receiver,
                        "msg_type": msg_type,
                        "content": content
                    })

    def checkpoint_environment(self):
        """
        Creates a snapshot of the entire environment state (and agent local states).
        This is used for potential global backtracking if a system-wide conflict arises.
        """
        snapshot = {
            "time": self.current_time,
            "message_pool": copy.deepcopy(self.message_pool.messages),
            "agents_state": {}
        }
        for agent in self.people:
            snapshot["agents_state"][agent.name] = copy.deepcopy(agent.local_state)
        self.global_history[self.current_time] = snapshot

    def revert_environment(self, target_time):
        """
        Reverts the environment state (and all agent local states) to the snapshot 
        at 'target_time'. Any messages or states introduced after 'target_time' are discarded.
        """
        if target_time not in self.global_history:
            return  # Invalid or no snapshot for that time

        snapshot = self.global_history[target_time]
        # Revert message pool
        self.message_pool.messages = copy.deepcopy(snapshot["message_pool"])
        # Revert each agent's local state
        for agent in self.people:
            if agent.name in snapshot["agents_state"]:
                agent.local_state = copy.deepcopy(snapshot["agents_state"][agent.name])
        # Adjust the current_time backward
        self.current_time = target_time
        # Discard any snapshots after target_time
        for t in sorted(list(self.global_history.keys())):
            if t > target_time:
                del self.global_history[t]

    def raise_conflict(self, details):
        """
        Raises a global conflict flag within the environment. 
        Typically invoked by a Verifier, Supervisor, or Controller agent 
        upon detecting unrecoverable local conflicts.
        """
        self.global_conflict_raised = True
        self.conflict_details = details

    def resolve_conflict(self):
        """
        Example conflict resolution strategy:
          1. Identify the last consistent checkpoint in self.global_history
          2. Revert environment to that checkpoint
          3. Clear conflict flags
        Alternatively, consult a Supervisor/Controller agent to pick the rollback point.
        """
        # By default, revert to the earliest or the most recent checkpoint
        # in which no conflict had been detected. For demonstration, 
        # revert to (current_time - 1) if it exists.
        fallback_time = self.current_time - 1
        while fallback_time >= 0:
            if fallback_time in self.global_history:
                self.revert_environment(fallback_time)
                break
            fallback_time -= 1
        self.global_conflict_raised = False
        self.conflict_details = None

    def run_time_step(self):
        """
        Advances the environment’s time by one increment. 
        Each agent can potentially run a local step or check for messages.
        """
        self.current_time += 1
        # Checkpoint environment state at the start or end of each step
        self.checkpoint_environment()

        # Run each agent's single-step logic
        for agent in self.people:
            agent.run_one_step()

        # If a conflict has been raised at any point:
        if self.global_conflict_raised:
            self.resolve_conflict()

    def run_until_stable(self, max_iterations=50):
        """
        Runs the environment repeatedly until no more conflicts are encountered
        or a maximum number of iterations is reached.
        """
        iteration_count = 0
        while iteration_count < max_iterations:
            self.run_time_step()
            iteration_count += 1

            # If no conflict is raised and everything is stable, we might break
            # In a real system, we might also check if tasks are complete
            if not self.global_conflict_raised:
                # Potential check if all agents are done
                pass

    def start(self):
        """
        Placeholder method. In a typical usage scenario, 
        you call run_until_stable or run_time_step in a loop.
        """
        self.run_until_stable()
