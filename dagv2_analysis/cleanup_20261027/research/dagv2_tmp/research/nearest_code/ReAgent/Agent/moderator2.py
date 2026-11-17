# =========================================================================================
# Moderator2 
# =========================================================================================
# This Moderator2 class builds on the same multi-step reasoning pipeline but allows
# optional external agents: Human (for interactive interventions) and BlackSheep (for
# adversarial or error-inducing participation). It integrates with the multi-agent system
# to potentially gather votes on each step, handle local or global backtracking, and
# incorporate user overrides via the Human agent.
#
# Core Differences from 'moderator.py':
#   1. Multi-Agent Voting:
#      - Observes votes from group.people, including specialized agents (Human, BlackSheep).
#   2. Potential Intervention:
#      - If the Human agent decides to interrupt or revert the chain-of-thought,
#        Moderator2 can comply by adjusting the reasoning flow.
#   3. Adversarial Influence:
#      - If BlackSheep is present, it may misleadingly force the system to re-check or revise.
#   4. Extra Steps to Revisit:
#      - Allows post-step discussion round if majority votes for revision.
# =========================================================================================

import json
import time

from Agent.agent import Agent
from backend.api import api_call
from Interaction.messagepool import message_pool


class Moderator2(Agent):
    """
    Moderator2 orchestrates a more advanced multi-step reasoning process with
    optional external agents like Human or BlackSheep. At each step:
      1. Gathers the partial chain-of-thought from the LLM.
      2. If multi-agent collaboration is enabled, obtains votes from group.people.
         - If the majority indicates revision is needed, triggers a discussion round.
      3. Supports user interventions (via a Human agent) that may override or skip backtracking.
      4. Concludes once a final answer is produced or a limit is reached.
    """

    _name = "moderator2"

    def __init__(self, name: str = None, model: str = "deepseek-chat"):
        """
        :param name: The Moderator2 agent's name; defaults to the class-level if None.
        :param model: Identifier of the language model to be used.
        """
        super().__init__(name=name if name is not None else self._name, model=model)
        self.user_message = None
        self.steps = []
        self.final_answer = None
        self.args = None

    def generate_o1_response(self, question: str):
        """
        A generator function that fetches chain-of-thought steps in JSON format from the LLM.
        1. Submits an initial prompt specifying multi-step reasoning in JSON with keys
           { "step", "reasoning", "next_action" }.
        2. Loops until "next_action" is 'final_answer' or step_count > 25.
        3. Yields partial steps for any external observer or orchestrator to handle them.
        4. Finally requests a plain-text final answer from the model.
        """
        step_count = 1
        total_thinking_time = 0

        # Construct messages
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert in multi-step reasoning tasks. The user has provided a question. "
                    "You must strictly return JSON outputs with keys: { \"step\", \"reasoning\", \"next_action\" }."
                    "If you have a final answer, set \"next_action\" to \"final_answer\"."
                )
            },
            {"role": "user", "content": question},
            {
                "role": "assistant",
                "content": "Alright, I will proceed with multi-step JSON-based reasoning."
            }
        ]

        # Repetitive steps flow
        while True:
            # If user_message is updated externally, attach it
            if self.user_message is not None:
                messages.append({
                    "role": "user",
                    "content": json.dumps(self.user_message, ensure_ascii=False)
                })

            start_time = time.time()
            step_data = None

            # Attempt multiple times to get valid JSON
            for attempt in range(10):
                try:
                    step_data = api_call(
                        messages,
                        model=self.model,
                        temperature=self.args.temperature if self.args else 1.0,
                        max_tokens=2048,
                        json_format=True
                    )
                    if "step" in step_data and "reasoning" in step_data and "next_action" in step_data:
                        break
                except Exception:
                    time.sleep(1)

            end_time = time.time()
            step_time = end_time - start_time
            total_thinking_time += step_time

            # If step_data is invalid after multiple attempts, break
            if not step_data:
                break

            # Record the step
            messages.append({
                "role": "assistant",
                "content": json.dumps(step_data, indent=4, ensure_ascii=False)
            })
            self.steps.append((f"Step {step_count}: {step_data['step']}", step_data['reasoning'], step_time))

            # Prepare for next step
            step_count += 1
            ref = step_data.get("next_action", None)

            # If there's a next action that isn't final_answer, ask the LLM to proceed
            if ref and ref != "final_answer":
                messages.append({
                    "role": "user",
                    "content": (
                        f"Proceed with next action '{ref}' in JSON format. "
                        "Do not produce an empty output."
                    )
                })
            else:
                # If 'final_answer' or no next_action, end loop
                break

            # Break if we exceed 25 steps
            if step_count > 25:
                break

            # Yield after each step
            yield self.steps, None

        # Request a final plain-text answer if next_action was 'final_answer'
        messages.append({
            "role": "user",
            "content": (
                "Now provide a final, plain-text answer. "
                "Avoid JSON. Summarize clearly without extraneous structure."
            )
        })
        start_time = time.time()
        final_text = api_call(
            messages,
            self.model,
            self.args.temperature if self.args else 1.0,
            300,
            json_format=False
        )
        end_time = time.time()
        final_time = end_time - start_time
        total_thinking_time += final_time

        # Append to steps
        self.steps.append(("Final Answer", final_text, final_time))
        yield self.steps, total_thinking_time

    def o1think(self, task, knowledges, group, args):
        """
        The main method for orchestrating multi-step JSON-based reasoning with optional
        multi-agent collaboration. Similar to the first Moderator, but can integrate Human
        or BlackSheep if they appear in 'group.people'.

        Steps:
          1. Prepare a detailed chain-of-thought prompt.
          2. Retrieve steps from generate_o1_response in a loop.
          3. After each step, if multi-agent system is active, gather votes for revision.
             If majority calls for revision, trigger a short discussion round in group.start().
          4. Return the final answer and the full list of steps.

        :param task: An object containing at least 'question'.
        :param knowledges: Additional textual knowledge or context.
        :param group: A container with multiple agents (including optional Human or BlackSheep).
        :param args: Configuration including 'temperature', 'mas', etc.
        :return: (final_answer, steps) The final answer text and the entire step history.
        """
        self.args = args
        question_text = f"Question: {task.question}\nKnowledge: {knowledges}\n"

        final_ans = None
        all_steps = None

        # Start iterative reasoning
        for all_steps, total_time in self.generate_o1_response(question_text):
            # The last step in all_steps is the current state
            if not all_steps:
                continue
            current_step, reasoning, _ = all_steps[-1]

            # Print or log the newest step
            self.say(f"{current_step}\n{reasoning}")

            # Check if it is a Final Answer step
            if current_step == "Final Answer":
                final_ans = reasoning
                break

            # If multi-agent collaboration is disabled, skip
            if not args.mas:
                continue

            # Otherwise, gather votes from the group
            vote_results = [agent.vote(task.question, knowledges) for agent in group.people]
            if sum(vote_results) > (len(vote_results) / 2):
                # Revision is needed
                recent_msgs = message_pool.get_visibile_messages()[1:]
                partial_content = "\n".join([f"{m.send_from}: {m.content}" for m in recent_msgs])
                summary, history = group.start(
                    n_round=2,
                    task=task,
                    current_step=f"{current_step}\n{reasoning}",
                    preious_content=partial_content,
                    knowledges=knowledges
                )
                # The environment returns a "summary" that modifies self.user_message
                self.user_message = summary
                all_steps[-1] = (all_steps[-1], history)
            else:
                # No revision needed
                all_steps[-1] = (all_steps[-1], None)

        return final_ans, all_steps


def main():
    """
    Example usage of Moderator2 in a scenario with optional external agents.
    In an actual implementation, 'group' might contain a Human or BlackSheep agent,
    and 'args' might indicate 'mas=True' for multi-agent synergy.
    """
    from Environment.environment import Environment  # hypothetical environment class

    # Sample setup
    mod2 = Moderator2(name="AdvancedModerator", model="deepseek-chat")
    class DummyTask:
        question = "Explain the cause of a solar eclipse."

    class DummyArgs:
        temperature = 1.0
        mas = True  # enable multi-agent synergy

    task = DummyTask()
    knowledge_stub = "Solar eclipse occurs when the moon blocks the sun's light from the earth."
    group = Environment(people=[])  # Suppose we have multiple specialized agents

    final_answer, step_history = mod2.o1think(
        task=task,
        knowledges=knowledge_stub,
        group=group,
        args=DummyArgs()
    )

    print("\n===== Final Answer =====")
    print(final_answer)


if __name__ == "__main__":
    main()
