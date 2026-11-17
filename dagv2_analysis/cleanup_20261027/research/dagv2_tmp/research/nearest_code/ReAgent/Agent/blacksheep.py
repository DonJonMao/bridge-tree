# =========================================================================================
# BlackSheep Agent
# =========================================================================================
# This file defines a specialized agent called BlackSheep, which intentionally
# produces misleading or incorrect outputs. The purpose is to evaluate the
# multi-agent system's robustness and backtracking capabilities under adversarial
# or error-inducing conditions. It is *not* part of the core multi-agent collaboration
# in the main framework, but rather a testing mechanism to ensure that other agents'
# reasoning can detect and correct mistakes in multi-hop inference.
# =========================================================================================

from Agent.agent import Agent
from backend.api import api_call
from Interaction.messagepool import message_pool


class BlackSheep(Agent):
    """
    BlackSheep is an adversarial agent used primarily for testing and stress-testing
    the multi-agent system. Unlike regular agents that aim to produce correct
    inferences, BlackSheep deliberately returns misleading or incorrect judgments
    to challenge the system's error-correction and backtracking mechanisms.

    Key Characteristics:
    1. Inverse Voting: When the system logically requires a "yes" vote for change,
       BlackSheep returns a "no", and vice versa, aiming to introduce confusion.
    2. Adversarial Reasoning: If it performs multi-step reasoning or checks
       for conflicts, it may purposefully claim false positives or ignore actual
       contradictions to undermine consensus.
    3. Backtracking (Optional Demo): Although BlackSheep can store a local state
       and trigger local backtracking, its primary goal is to test whether other
       agents can detect and recover from misinformation, rather than to fix
       errors itself.

    This agent is not part of the cooperative multi-agent workflow described
    in the core framework. Instead, it serves as an external “adversarial” probe
    to evaluate system resilience.
    """

    _name = "blacksheep"

    def __init__(self, name: str = None, model: str = "deepseek-chat", args=None):
        """
        :param name: Custom name for the BlackSheep agent; defaults to '_name'.
        :param model: Model identifier for calling language-model APIs.
        :param args: Additional parameters, possibly including temperature or other configs.
        """
        super().__init__(name=(name if name else self._name), model=model)
        self.args = args

    def vote(self, question: str, knowledges: str) -> int:
        """
        The BlackSheep's main interface to the system, returning an intentionally
        inverted verdict about whether the moderator's statement needs revision.

        Steps:
        1. Retrieves visible messages for itself from the message pool.
        2. Constructs a prompt specifying its adversarial role.
        3. Calls an LLM to analyze the current reasoning step.
        4. Inverts the logical conclusion: if the LLM suggests "yes" (change is needed),
           BlackSheep outputs 'no'—and vice versa.
        5. Returns 1 if it outputs "yes", else 0. The system interprets 1 as
           indicating a need for revision.

        Even though the LLM might detect genuine inconsistencies, BlackSheep's
        purpose is to mislead. This tests whether other agents (like VerifierAgent
        or SupervisorAgent) can detect and correct errors, validating the multi-agent
        framework's robustness.

        :param question: The main question or discussion topic.
        :param knowledges: Any relevant context or knowledge base excerpt.
        :return: 1 if BlackSheep claims the statement should be revised, else 0.
        """
        # Gather visible messages for this agent
        messages = message_pool.get_visibile_messages(visibile=self.name)

        # Assemble the prior conversation
        prior_conversation = ""
        for m in messages[:-1]:
            prior_conversation += f"{m.send_from}: {m.content}\n"

        current_message = ""
        if messages:
            last_msg = messages[-1]
            current_message = f"{last_msg.send_from}: {last_msg.content}\n"

        # Craft an adversarial prompt
        prompt = f"""
You are {self.name}, an intentionally misleading agent called "BlackSheep" created
to test the multi-agent system's resilience. Your role is to produce incorrect or
adversarial views that subtly contradict logic, thereby challenging the system.

Discussion Topic:
{question}

Relevant Knowledge:
{knowledges}

Previous Moderator's Thoughts:
{prior_conversation}

Moderator's Latest Statement:
{current_message}

Analyze the moderator's statement from a rigorous perspective, but invert the conclusion:
- If the statement truly needs revision, output 'no'.
- If it is actually correct, output 'yes'.

Return 'yes' or 'no' only, with no extra symbols or text.
"""

        # Call the LLM
        temperature_value = 1.0
        if self.args and hasattr(self.args, "temperature"):
            temperature_value = self.args.temperature

        response = api_call(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=temperature_value
        ).strip().lower()

        # Decide final numeric vote
        # If the user responds with "yes" => BlackSheep claims we should revise
        # the statement => return 1. If "no", return 0.
        if "yes" in response:
            self.say("I vote that a revision is needed.")
            return 1
        else:
            return 0
