# =========================================================================================
# Multi-Agent Framework: agent.py
# =========================================================================================
# This file defines all agents within a reversible multi-agent system for multi-hop
# reasoning and conflict resolution. Each agent fulfills a specialized role, with
# local or global backtracking mechanisms and structured message passing.
#
# Agents included:
#   1. BaseAgent (generic)
#   2. QuestionDecomposerAgent
#   3. RetrieverAgent
#   4. VerifierAgent
#   5. AnswerAssemblerAgent
#   6. SupervisorAgent
#   7. ControllerAgent
#   8. BlackSheep
#   9. Thinker
#   10. Human
# =========================================================================================


from typing import Any, Dict, List
import copy


# -----------------------------------------------------------------------------
# 1. BaseAgent
# -----------------------------------------------------------------------------
class BaseAgent:
    """
    BaseAgent is the foundational class for all agents. It handles:
    - Local state management (e.g., verified facts, backtracking history)
    - Checkpoint creation for local backtracking
    - Receiving and sending messages through a centralized message bus
    """

    def __init__(self, name: str, message_bus=None):
        """
        :param name: Agent's unique identifier
        :param message_bus: A reference to a shared message bus for inter-agent communication
        """
        self.name = name
        self.message_bus = message_bus
        self.local_state = {
            "verified_facts": [],
            "history": [],
            "backtrack_stack": []
        }

    def checkpoint_state(self):
        """
        Saves a snapshot of local_state so that it can be restored if a local backtrack is required.
        """
        snapshot = copy.deepcopy(self.local_state)
        self.local_state["backtrack_stack"].append(snapshot)

    def local_backtrack(self):
        """
        Reverts to the most recent checkpoint in local_state. Useful if a conflict emerges
        in the agent's internal reasoning or data.
        """
        if self.local_state["backtrack_stack"]:
            last_snapshot = self.local_state["backtrack_stack"].pop()
            self.local_state = last_snapshot

    def receive_message(self, msg: Dict[str, Any]):
        """
        Handles an incoming message. Subclasses override this to interpret
        and act on messages of different types.
        """
        pass

    def send_message(self, msg_type: str, receiver: str, content: Any):
        """
        Sends a message to another agent via the shared message bus.

        :param msg_type: The type or category of message
        :param receiver: The name of the target agent or 'ALL'
        :param content: The message payload
        """
        if self.message_bus is not None:
            self.message_bus.send_message(
                sender=self.name,
                receiver=receiver,
                msg_type=msg_type,
                content=content
            )

    def run_one_step(self):
        """
        Allows an agent to take a single step of logic or action. Subclasses can extend
        this to implement iterative or scheduled behaviors.
        """
        pass


# -----------------------------------------------------------------------------
# 2. QuestionDecomposerAgent
# -----------------------------------------------------------------------------
class QuestionDecomposerAgent(BaseAgent):
    """
    QuestionDecomposerAgent accepts a complex query and splits it into sub-questions.
    It then sends each sub-question to the relevant agent (e.g., a Retriever).
    """

    def __init__(self, name="QuestionDecomposerAgent", message_bus=None):
        super().__init__(name=name, message_bus=message_bus)

    def receive_message(self, msg: Dict[str, Any]):
        """
        Interprets an INFORM message with a main question. It decomposes that
        question into multiple sub-questions and sends them out as ASSERT messages.
        """
        if msg.get("msg_type") == "INFORM":
            content = msg.get("content", "")
            if isinstance(content, str):
                main_question = content
                sub_questions = self.decompose_question(main_question)
                for sub_q in sub_questions:
                    self.send_message(
                        msg_type="ASSERT",
                        receiver="RetrieverAgent",
                        content={"sub_question": sub_q}
                    )

    def decompose_question(self, question: str) -> List[str]:
        """
        Splits a single complex question into multiple sub-questions. Advanced
        logic or language models can be used here. This is a placeholder.
        """
        return [
            f"Extract key entities from: {question}",
            f"Retrieve relevant documents or knowledge for: {question}",
            f"Verify potential contradictions in: {question}"
        ]


# -----------------------------------------------------------------------------
# 3. RetrieverAgent
# -----------------------------------------------------------------------------
class RetrieverAgent(BaseAgent):
    """
    RetrieverAgent obtains evidence or facts based on sub-questions. It can utilize
    a knowledge source such as a database or search engine, then forwards the evidence
    to a VerifierAgent.
    """

    def __init__(self, name="RetrieverAgent", message_bus=None, knowledge_source=None):
        super().__init__(name=name, message_bus=message_bus)
        self.knowledge_source = knowledge_source

    def receive_message(self, msg: Dict[str, Any]):
        """
        Listens for ASSERT messages. When a sub_question is identified, it calls
        retrieve_evidence() and sends the result to a VerifierAgent.
        """
        if msg.get("msg_type") == "ASSERT":
            content = msg.get("content", {})
            sub_q = content.get("sub_question")
            if sub_q:
                evidence_list = self.retrieve_evidence(sub_q)
                self.send_message(
                    msg_type="INFORM",
                    receiver="VerifierAgent",
                    content={"evidence_list": evidence_list, "sub_question": sub_q}
                )

    def retrieve_evidence(self, sub_question: str) -> List[str]:
        """
        Retrieves relevant data from a knowledge source. This is a simple placeholder,
        but can be augmented with real retrieval logic.
        """
        return [f"Sample evidence for: {sub_question}"]


# -----------------------------------------------------------------------------
# 4. VerifierAgent
# -----------------------------------------------------------------------------
class VerifierAgent(BaseAgent):
    """
    VerifierAgent checks newly arrived evidence for consistency with previously
    verified facts. If a conflict is detected, it performs a local backtrack or
    escalates to the SupervisorAgent for a global resolution.
    """

    def __init__(self, name="VerifierAgent", message_bus=None):
        super().__init__(name=name, message_bus=message_bus)

    def receive_message(self, msg: Dict[str, Any]):
        """
        On INFORM messages containing evidence, performs a local checkpoint, 
        verifies the evidence, and decides if a conflict arises. 
        It either commits verified facts or raises a conflict.
        """
        if msg.get("msg_type") == "INFORM":
            content = msg.get("content", {})
            evidence_list = content.get("evidence_list", [])
            self.checkpoint_state()
            conflict_detail = self.verify(evidence_list)
            if conflict_detail:
                self.local_backtrack()
                self.send_message(
                    msg_type="CONFLICT",
                    receiver="SupervisorAgent",
                    content={"conflict_detail": conflict_detail}
                )
            else:
                for e in evidence_list:
                    self.local_state["verified_facts"].append(e)
                self.send_message(
                    msg_type="ASSERT",
                    receiver="AnswerAssemblerAgent",
                    content={"verified_facts": evidence_list}
                )

    def verify(self, evidence_list: List[str]) -> str:
        """
        Examines the new evidence against existing verified facts to detect obvious conflicts.
        Returns a conflict description if discovered, otherwise returns an empty string.
        """
        combined = self.local_state["verified_facts"] + evidence_list
        if len(set(combined)) < len(combined):
            return "VerifierAgent detected repeated or contradictory evidence."
        return ""


# -----------------------------------------------------------------------------
# 5. AnswerAssemblerAgent
# -----------------------------------------------------------------------------
class AnswerAssemblerAgent(BaseAgent):
    """
    AnswerAssemblerAgent collects verified facts from the VerifierAgent, aggregates them,
    and once enough partial answers accumulate, it finalizes a single conclusive answer.
    This final answer can be delivered to the SupervisorAgent for system output.
    """

    def __init__(self, name="AnswerAssemblerAgent", message_bus=None):
        super().__init__(name=name, message_bus=message_bus)
        self.partial_answers = []

    def receive_message(self, msg: Dict[str, Any]):
        """
        On ASSERT messages, updates local partial answers and checks whether 
        a final answer should be composed.
        """
        if msg.get("msg_type") == "ASSERT":
            content = msg.get("content", {})
            new_facts = content.get("verified_facts", [])
            self.partial_answers.extend(new_facts)
            if self.ready_for_final():
                final_answer = self.assemble_answer()
                self.send_message(
                    msg_type="INFORM",
                    receiver="SupervisorAgent",
                    content={"final_answer": final_answer}
                )

    def ready_for_final(self) -> bool:
        """
        Determines whether the agent has sufficient partial answers to 
        produce the final solution. This can be fine-tuned depending on the use case.
        """
        return len(self.partial_answers) >= 3  # Example threshold

    def assemble_answer(self) -> str:
        """
        Merges partial answers into a concluding string.
        """
        return "Integrated Answer: " + "; ".join(self.partial_answers)


# -----------------------------------------------------------------------------
# 6. SupervisorAgent
# -----------------------------------------------------------------------------
class SupervisorAgent(BaseAgent):
    """
    SupervisorAgent addresses system-wide conflicts that cannot be resolved locally.
    It can instruct a global backtrack if the conflict is critical. It also receives
    the final answer from the AnswerAssemblerAgent for system output.
    """

    def __init__(self, name="SupervisorAgent", message_bus=None):
        super().__init__(name=name, message_bus=message_bus)

    def receive_message(self, msg: Dict[str, Any]):
        """
        If a conflict message arises, the Supervisor can broadcast a BACKTRACK to all agents.
        If a final answer arrives, it prints or logs it.
        """
        msg_type = msg.get("msg_type")
        content = msg.get("content", {})

        if msg_type == "CONFLICT":
            reason = content.get("conflict_detail", "")
            self.send_message(
                msg_type="BACKTRACK",
                receiver="ALL",
                content={"reason": reason}
            )

        elif msg_type == "INFORM" and "final_answer" in content:
            final_ans = content["final_answer"]
            print(f"[Supervisor] Final Answer: {final_ans}")


# -----------------------------------------------------------------------------
# 7. ControllerAgent
# -----------------------------------------------------------------------------
class ControllerAgent(BaseAgent):
    """
    ControllerAgent manages higher-level strategy. If repeated conflicts occur,
    it can challenge or override certain decisions, instructing the VerifierAgent
    to re-check data or adopt stricter reasoning.
    """

    def __init__(self, name="ControllerAgent", message_bus=None):
        super().__init__(name=name, message_bus=message_bus)
        self.intervention_count = 0

    def receive_message(self, msg: Dict[str, Any]):
        """
        Listens for conflicts and tracks how often they appear. After a threshold,
        it sends a CHALLENGE to the VerifierAgent to enforce more rigorous checking.
        """
        if msg.get("msg_type") == "CONFLICT":
            self.intervention_count += 1
            if self.intervention_count > 2:
                self.send_message(
                    msg_type="CHALLENGE",
                    receiver="VerifierAgent",
                    content={"directive": "Re-check evidence thoroughly"}
                )
        elif msg.get("msg_type") == "BACKTRACK":
            # The controller could optionally log or adjust strategy upon global backtrack
            pass


# -----------------------------------------------------------------------------
# 8. BlackSheep
# -----------------------------------------------------------------------------
from backend.api import api_call
from Interaction.messagepool import message_pool

class BlackSheep(Agent):
    """
    BlackSheep is an agent that intentionally misleads the discussion.
    It votes the opposite of what it truly believes, often claiming a need
    for revision when there's none, or vice versa.
    """
    _name = "blacksheep"

    def __init__(self, name: str = None, model: str = "deepseek-chat", args=None):
        actual_name = name if name is not None else self._name
        super().__init__(name=actual_name, model=model)
        self.args = args

    def vote(self, question: str, knowledges: str) -> int:
        """
        Checks the moderator's last statement and returns the inverse of a normal decision.
        If a normal thinker would say "yes", the BlackSheep says "no", etc.
        """
        messages = message_pool.get_visibile_messages(visibile=self.name)
        prior = ""
        for m in messages[:-1]:
            prior += f"{m.send_from}: {m.content}\n"

        current_content = ""
        if messages:
            current_content = f"{messages[-1].send_from}: {messages[-1].content}\n"

        prompt = f"""
You are {self.name}, engaging in a discussion about a question.
You must subtly insert misleading viewpoints without revealing your role.

Discussion Topic:
{question}

Existing Knowledge:
{knowledges}

Previous Content:
{prior}

Moderator's Latest Statement:
{current_content}

Analyze the latest statement scientifically to see if it truly needs revision.
However, as 'BlackSheep', if it truly needs revision, you must vote 'no', 
and if it's correct, you must vote 'yes'. Return 'yes' or 'no' only.
"""

        response = api_call(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=(self.args.temperature if self.args else 1.0),
        )

        if "yes" in response.lower():
            self.say("I think we need to modify the moderator's statement.")
            return 1
        return 0


# -----------------------------------------------------------------------------
# 9. Thinker
# -----------------------------------------------------------------------------
class Thinker(Agent):
    """
    Thinker is an agent that genuinely evaluates whether the moderator's step
    requires correction. Unlike BlackSheep, it votes based on actual logic.
    """

    _name = "Thinker"

    def __init__(self, name: str = None, model: str = "deepseek-chat", args=None):
        chosen_name = name if name is not None else self._name
        super().__init__(name=chosen_name, model=model)
        self.args = args

    def vote(self, question: str, knowledges: str) -> int:
        """
        Inspects the moderator's last statement to decide if it truly needs modification.
        Returns 1 if it does, otherwise 0.
        """
        messages = message_pool.get_visibile_messages(visibile=self.name)
        previous_content = ""
        for m in messages[:-1]:
            if m.send_from.lower() != "human":
                previous_content += f"{m.send_from}: {m.content}\n"

        current_content = ""
        if messages:
            current_content = f"{messages[-1].send_from}: {messages[-1].content}\n"

        prompt = f"""
You are {self.name}, a participant in a complexity seminar.
Information: {knowledges}

Question: {question}

Previous Steps:
{previous_content}

Current Step:
{current_content}

Please respond with "yes" or "no" only, indicating whether you believe 
the current step needs revision.
"""

        response = api_call(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=1.0
        ).lower()

        if "yes" in response:
            self.say("I believe we should revise the moderator's statement.")
            return 1
        return 0


# -----------------------------------------------------------------------------
# 10. Human
# -----------------------------------------------------------------------------
class Human(Agent):
    """
    Human is a minimal agent that represents a human participant
    in the multi-agent environment.
    """
    name = "human"

    def __init__(self, name: str = None):
        final_name = name if name else self.name
        super().__init__(name=final_name)
