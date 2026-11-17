# =========================================================================================
# Moderator
# =========================================================================================
# This Moderator class coordinates a straightforward multi-agent reasoning process,
# consistent with the original multi-agent framework described in the paper. It does not
# include additional agents like Human or BlackSheep by default.
#
# Note:
#   - This file does NOT integrate the optional "Human" or "BlackSheep" agents. For a
#     more advanced approach, see "moderator2.py".
# =========================================================================================

import time
from Agent.agent import Agent
from backend.api import api_call_completion
from Interaction.messagepool import message_pool

class Moderator(Agent):
    """
    This Moderator orchestrates multi-step reasoning by prompting an LLM with
    a chain-of-thought request. It stops when it detects "Final Answer" or hits
    a maximum iteration threshold. By default, it does not incorporate external
    agents like Human or BlackSheep.
    """

    _name = "moderator"

    def __init__(self, name: str = None, model: str = "deepseek-v3"):
        """
        :param name: The Moderator's name. Defaults to '_name' if None.
        :param model: An identifier for the language model used in chain-of-thought.
        """
        super().__init__(name=name if name else self._name, model=model)
        self.current_text = None
        self.current_step = 1
        self.iteration = 0
        self.steps = []
        self.final_answer = None
        self.messages = []

    def generate_step_response(self, prompt: str):
        """
        A generator function that repeatedly queries the LLM using 'api_call_completion'.
        Each iteration:
          1. Sends the updated message history (including the previous step) to the LLM.
          2. Waits for a new step. We use 'stop_list=[f"Step {self.current_step+1}:"]'
             to break the output at the next step marker.
          3. Yields the raw step text.
        """
        self.messages = [{"role": "user", "content": prompt}]

        while True:
            if self.current_step != 1 and self.current_text:
                self.messages.append({
                    "role": "assistant",
                    "content": self.current_text
                })

            start_time = time.time()
            step_resp = api_call_completion(
                messages=self.messages,
                model=self.model,
                stop_list=[f"Step {self.current_step+1}:"]
            )
            end_time = time.time()

            thinking_time = end_time - start_time
            self.current_text = step_resp
            self.steps.append((step_resp, thinking_time))

            yield step_resp

    def cot(self, question: str, additional_knowledge: str = None, max_steps: int = 15):
        """
        The primary chain-of-thought (CoT) method:
        1. Builds a prompt requiring each step to begin with 'Step x:' and end with '[End]'.
        2. Iterates through the step responses until 'Final Answer' is found or 'max_steps'.
        3. Returns the final answer and the entire step list.

        :param question: The user query or problem to solve.
        :param additional_knowledge: Optional extra context or knowledge to embed in the prompt.
        :param max_steps: The maximum number of steps before stopping.
        :return: (final_answer, steps)
        """
        if additional_knowledge is None:
            additional_knowledge = ""

        chain_prompt = (
            f"{question}\n\n"
            "Please reason step by step. Each step starts with \"Step x:\" and ends with \"[End]\".\n"
            "If the problem is complex, you may use structured reasoning or tables.\n"
            "Conclude with a \"Final Answer:\" step.\n\n"
            "Example:\n"
            "Step 1: Explanation [End]\n"
            "Step 2: Reasoning [End]\n"
            "Final Answer: The final text [End]\n\n"
            f"Additional Knowledge:\n{additional_knowledge}\n"
        )

        final_flag = False
        final_answer_text = None

        # Start generating steps
        for step_text in self.generate_step_response(chain_prompt):
            self.iteration += 1
            # Print or log the step
            print(f"--- Step {self.current_step} Output Start ---\n{step_text}\n--- End ---")
            # Check for final answer
            if "Final Answer" in step_text and "[End]" in step_text:
                final_flag = True
                final_answer_text = step_text
                break
            if self.iteration >= max_steps:
                break

            self.current_step += 1

        return (final_answer_text, self.steps)


def main():
    """
    Basic usage demonstration. This minimal example does not show multi-agent voting,
    but references the same pipeline used in the rest of the system.
    """
    mod = Moderator(name="MyModerator", model="deepseek-v3")
    question = "Which US state hosted the 1984 Summer Olympics and has a smaller capital city than its largest city?"
    additional_knowledge = "Facts about US states, capitals, and city sizes."
    final_ans, steps = mod.cot(question, additional_knowledge)

    print("\n===== Final Answer =====")
    print(final_ans)

if __name__ == "__main__":
    main()
