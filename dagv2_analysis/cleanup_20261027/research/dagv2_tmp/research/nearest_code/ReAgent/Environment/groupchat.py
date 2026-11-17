# =========================================================================================
# groupchat.py
# =========================================================================================
# This file extends the Environment class into a GroupChatEnvironment that allows
# multiple rounds of agent discussion and a dynamic trust-graph. The environment can
# incorporate concurrency, conflict backtracking, and trust updates. It aligns 
# with the paper’s three-layer approach and shows how knowledge exchange can 
# evolve over multiple time steps or rounds.
# =========================================================================================

import time
import copy
from Environment.environment import Environment
from Interaction.messagepool import MessagePool, Message
from backend.api import api_call

class GroupChatEnvironment(Environment):
    """
    GroupChatEnvironment enhances the base Environment with a round-based or 
    multi-phase discussion model. Agents can produce messages in each round, 
    update trust levels, and optionally perform partial or global backtracking.

    Key Features:
      1. Trust Graph: Each agent has a trust score for every other agent. 
         The environment updates these scores after each discussion round.
      2. Round-Based Discussion: Repeated cycles of message creation, 
         retrieval, and potential conflict resolution.
      3. Integration with Concurrency: Inherits from Environment, which 
         supports a time-step model, backtracking snapshots, and conflict signals.
    """

    def __init__(self, people: list, args):
        """
        :param people: A list of participant/agent objects that will partake in the chat.
        :param args: Configuration dict or object for environment-level parameters.
        """
        super().__init__(people=people, args=args)
        self.trust_graph = self._initialize_trust_graph()
        # Possibly store additional group-level data (like aggregated discussions)
        self.discussion_history = []

    def _initialize_trust_graph(self):
        """
        Initializes each agent’s trust in every other agent to a default (e.g., 0.5).
        """
        trust_graph = {}
        for agent in self.people:
            trust_graph[agent.name] = {}
            for other in self.people:
                if other.name != agent.name:
                    trust_graph[agent.name][other.name] = 0.5
        return trust_graph

    def update_trust_score(self, evaluator, evaluatee, rating):
        """
        Updates the trust score for 'evaluatee' as given by 'evaluator'. 
        A rating might be 0..9. We'll map that to a small trust update around the 
        prior score in [0,1].
        """
        old_score = self.trust_graph[evaluator].get(evaluatee, 0.5)
        # Some learning rate or weighting logic
        lr = 0.1
        # rating 0 => -0.5 shift, rating 9 => +0.4 shift, etc.
        shift = 0.1 * rating - 0.45  # e.g. rating=5 => shift=0.05 => slight upward
        new_score = old_score + lr * shift
        # Bound in [0, 1]
        new_score = max(0.0, min(1.0, new_score))
        self.trust_graph[evaluator][evaluatee] = new_score

    def summary_of_round(self, round_index):
        """
        Produces a summary of the most recent messages in the environment’s message pool, 
        focusing on the messages introduced in this round. This can be used for 
        real-time feedback or logging.
        """
        # For demonstration, gather all messages from this time step or the entire pool.
        # Real logic might store the last round’s message IDs or timestamps.
        summary_content = "\n".join(
            f"{m.send_from}: {m.content}" for m in self.message_pool.messages
        )
        return f"Round {round_index} Summary:\n{summary_content}"

    def run_round(self, round_index):
        """
        Executes a single discussion round. Each agent can produce a new message 
        (depending on their internal logic), after which trust and conflict checks 
        may be triggered.
        """
        # The environment increments time or takes a snapshot before the round
        self.checkpoint_environment()

        # Let each agent produce or consume messages
        for agent in self.people:
            # Each agent might generate a message or check for conflicts
            agent.run_one_step()

        # Conflict check (if raised by any agent):
        if self.global_conflict_raised:
            self.resolve_conflict()

        # Post-round trust updates or other aggregator logic could go here
        # e.g., we can prompt each agent to rate others’ statements
        # For brevity, we skip the full rating-prompt code. Instead, we could do:
        """
        for evaluator in self.people:
            for evaluatee in self.people:
                if evaluatee != evaluator:
                    rating = self.obtain_rating(evaluator, evaluatee)
                    self.update_trust_score(evaluator.name, evaluatee.name, rating)
        """

        # Summarize the round if needed
        summary = self.summary_of_round(round_index)
        self.discussion_history.append(summary)

    def start_discussion(self, n_rounds=3):
        """
        Simple API to run a multi-round discussion. 
        Each round calls run_round(...).
        """
        for i in range(n_rounds):
            print(f"\n=== Starting Round {i} ===")
            self.run_round(i)
            print(self.discussion_history[-1])

    # Optionally, you can override the base start method 
    # to integrate run_until_stable with multi-round discussion
    def start(self):
        """
        Example integrated method that merges multi-round discussion with
        the concurrency/time-step approach from the base environment.
        """
        # We can combine time-stepped logic with round-based discussion if needed:
        self.start_discussion(n_rounds=3)
        # Or run until stable if the design calls for continuous concurrency
        self.run_until_stable(max_iterations=20)
