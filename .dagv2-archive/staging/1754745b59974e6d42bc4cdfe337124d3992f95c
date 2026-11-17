```python
# =========================================================================================
# Thinker
# =========================================================================================
# The Thinker is designed to evaluate whether the Moderator's most recent
# reasoning step requires correction. It is coordinating with Moderator, Verifier and Supervisor).
#
# Enhancements in this version:
#   1. Aligned with the updated multi-agent pipeline as described in the improved Moderator.
#   2. Supports optional local backtracking if Thinker repeatedly detects issues that
#      are not addressed by the system.
#   3. Incorporates additional commentary and error-checking for improved resilience,
#      including synergy with the new chain-of-thought approach.
# =========================================================================================

from Agent.agent import Agent
from backend.api import api_call
from Interaction.messagepool import message_pool

class Thinker(Agent):
    """
    Thinker is an agent class that inspects the Moderator's current reasoning step
    and decides if it should be revised. By retrieving relevant conversation history
    from the message pool, it determines whether logical flaws, factual inconsistencies,
    or other errors appear, then casts a vote ('yes' or 'no') accordingly.

    Key Updates:
      - Incorporates synergy with the newly improved Moderator classes,
        which may generate multi-step reasoning in a chain-of-thought style.
      - Supports optional local backtracking if repeated conflicts or unexpected conditions
        arise, demonstrating advanced internal state handling.
    """

    _name = "Thinker"

    def __init__(self, name: str = None, model: str = "deepseek-chat", args=None):
        """
        :param name: Custom name for the Thinker agent; defaults to the class-level _name if None.
        :param model: The model identifier for external LLM API calls (e.g., 'deepseek-chat').
        :param args: Configuration object (e.g., specifying 'temperature' or 'debug' flags).
        """
        super().__init__(name=name if name is not None else self._name, model=model)
        self.args = args
        # This agent can track a small local backtracking stack for repeated conflict signals
        self.conflict_count = 0

    def vote(self, question: str, knowledges: str) -> int:
        """
        Inspects the conversation history to judge if the Moderator's latest reasoning step
        needs modification. Returns:
          1 => 'yes' vote to revise the Moderator's reasoning
          0 => 'no' vote to keep it as is.

        Workflow:
          1. Retrieve messages visible to this agent from the message pool.
          2. Collect the Moderator’s reasoning steps (excluding human interventions if present).
          3. Construct a prompt requesting a concise "yes"/"no" decision about revision.
          4. Parse the LLM response; if "yes," we also call self.say(...) to log the decision.
          5. Increment local conflict counters if repeated "yes" is returned, illustrating
             potential local backtracking usage.

        :param question: The question under discussion, used as context in the prompt.
        :param knowledges: A string representing relevant knowledge or context.
        :return: Integer 1 if we vote to revise, 0 otherwise.
        """
        # Gather visible messages for Thinker
        messages = message_pool.get_visibile_messages(visibile=self.name)

        # Compile prior content from the Moderator or other participants
        previous_content = ""
        if len(messages) > 1:
            for msg in messages[:-1]:
                if msg.send_from.lower() not in ("human"):
                    previous_content += f"{msg.send_from}: {msg.content}\n"

        # The latest message is presumably the Moderator's current step
        current_message = ""
        if messages:
            last_msg = messages[-1]
            current_message = f"{last_msg.send_from}: {last_msg.content}\n"

        # Build an LLM prompt to detect errors or flaws
        prompt = f"""You are {self.name}, analyzing the moderator's latest reasoning step.
Information: {knowledges}

Question: {question}

-- Previous Steps from the Moderator or others --
{previous_content}

-- Current Step --
{current_message}

Instructions:
1. Check if there are any contradictions, logical flaws, or miscalculations.
2. Return only "yes" or "no":
   - "yes" => The step truly needs revision.
   - "no"  => The step is acceptable as is.
No extra text or symbols are allowed.
"""

        # Call the LLM
        temperature_val = 1.0
        if self.args and hasattr(self.args, 'temperature'):
            temperature_val = self.args.temperature

        response = api_call(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=temperature_val
        ).strip().lower()

        # Determine final vote
        if "yes" in response:
            self.say("I believe the moderator's step should be revised.")
            self.conflict_count += 1

            # (Optional) local backtracking trigger after repeated conflict signals
            # If the conflict_count is high, we might revert to a local checkpoint
            if self.conflict_count > 3:
                self.local_backtrack()
                self.conflict_count = 0

            return 1
        else:
            return 0

    def receive_message(self, msg):
        """
        This agent does not perform specialized behavior on incoming messages
        outside of the vote() method. However, you could implement additional
        checks here, e.g., if a Supervisor or Controller broadcasts a message
        about a conflict or asks the Thinker for specific feedback.
        """
        pass
```
