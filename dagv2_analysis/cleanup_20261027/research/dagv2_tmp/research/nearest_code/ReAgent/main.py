# =========================================================================================
# main.py
# =========================================================================================
# This file demonstrates how to wire together the entire multi-agent system at the
# highest level. It showcases:
#   - Reading in a dataset (e.g., HotpotQA) or provided data
#   - Instantiating core agents (QuestionDecomposer, Retriever, Verifier, AnswerAssembler,
#     Supervisor, Controller) alongside optional agents (Thinker, Human, BlackSheep)
#   - Configuring an Environment (e.g., GroupChatEnvironment) to manage concurrency,
#     backtracking, and trust updates
#   - Invoking one of the Moderator classes (e.g. Moderator2) to orchestrate
#     with multi-agent collaboration
#   - Running the entire pipeline and printing or logging final answers
#
# =========================================================================================

import sys
import os

# Example: If your local project structure differs, adapt imports accordingly.
# Agents
from Agent.agent import Agent
from Agent.moderator2 import Moderator2  # The advanced moderator
from Agent.moderator import Moderator    # The simpler baseline moderator
from Agent.thinker import Thinker
from Agent.blacksheep import BlackSheep
from Agent.human import Human

# Environment
from Environment.environment import Environment
from Environment.groupchat import GroupChatEnvironment

# Interaction
from Interaction.messagepool import MessagePool, message_pool

# DataProcess
from DataProcess.Hotpotqa import HotpotQA
from DataProcess.Dataset import HotpotqaDataset

from Agent.agent import BaseAgent  

class Args:
    def __init__(self):
        self.model = "deepseek-chat"       # default model name for demonstration
        self.temperature = 1.0            # LLM temperature
        self.mas = True                   # whether multi-agent synergy is enabled
        self.truth = False                # whether to enable trust-based disclaimers
        self.dataset_path = "Your Path"  # default dataset path for demonstration
        self.debug = False                # debug flag for extra logging


def build_agents(agent_args):
    question_decomposer = BaseAgent(name="QuestionDecomposerAgent")
    retriever_agent     = BaseAgent(name="RetrieverAgent")
    verifier_agent      = BaseAgent(name="VerifierAgent")
    assembler_agent     = BaseAgent(name="AnswerAssemblerAgent")
    supervisor_agent    = BaseAgent(name="SupervisorAgent")
    controller_agent    = BaseAgent(name="ControllerAgent")

    # Optional agents
    thinker_agent       = Thinker(name="ThinkerAgent", model=agent_args.model, args=agent_args)
    black_sheep_agent   = BlackSheep(name="BlackSheepAgent", model=agent_args.model, args=agent_args)
    human_agent         = Human(name="HumanAgent")

    # Return a list of all agents (some might not be used if 'mas' is disabled, etc.)
    return [
        question_decomposer, retriever_agent, verifier_agent, assembler_agent,
        supervisor_agent, controller_agent, thinker_agent, black_sheep_agent,
        human_agent
    ]


def load_hotpotqa_dataset(path):
    """
    Loads the HotpotQA dataset from the specified path. 
    If not found, warns and returns an empty list or partial fallback.
    """
    try:
        dataset = HotpotqaDataset(dataset_path=path)
        print(f"[INFO] Successfully loaded HotpotQA dataset from {path}, total {len(dataset.tasks)} tasks.")
        return dataset
    except FileNotFoundError:
        print(f"[WARN] HotpotQA dataset file not found at {path}. Returning a fallback dataset.")
        # Return an empty or dummy dataset for demonstration
        return None


def main():
    """
    The main entry point for running the entire multi-agent system.
    Provides:
      1. Argument/config setup
      2. Agent creation
      3. Environment instantiation
      4. Dataset loading
      5. Moderator orchestration (with chain-of-thought)
      6. Multi-agent synergy, optional backtracking, final answer output
    """
    # 1. Build arguments/config
    args = Args()

    # (Optional) parse CLI if desired, e.g.:
    # if len(sys.argv) > 1:
    #     args.dataset_path = sys.argv[1]
    #     # etc.

    # 2. Create the primary agent set
    agents = build_agents(args)

    # 3. Instantiate environment or group environment
    #    In the simplest scenario, we can do:
    #    env = Environment(people=agents, args=args)
    #    But let's use a GroupChatEnvironment for demonstration:
    env = GroupChatEnvironment(people=agents, args=args)

    # 4. (Optional) load the HotpotQA dataset
    dataset_obj = load_hotpotqa_dataset(args.dataset_path)

    # For demonstration, we can pick a single sample
    # If dataset_obj is valid and not None:
    if dataset_obj and len(dataset_obj.tasks) > 0:
        task_data = dataset_obj.tasks[0]  # pick first sample
        question_str = task_data.question
        knowledge_str = task_data.get_knowledge(args)  # or any string representation
    else:
        # fallback demonstration if dataset not loaded
        question_str = "Which US state hosted the 1984 Summer Olympics and has a smaller capital city than its largest city?"
        knowledge_str = "Additional facts: ..."  # user-provided or empty

    # 5. Initialize one of the advanced Moderator classes to run chain-of-thought
    #    Here we demonstrate Moderator2, which supports multi-agent synergy. 
    #    If you want a simpler baseline, use Moderator.
    #    We'll pass the same model as the rest of the system, or override if desired.

    advanced_moderator = Moderator2(name="AdvancedModerator", model=args.model)

    advanced_moderator.args = args  # so it has config info

    # 6. Optionally start environment concurrency or multi-round chat
    #    env.start_discussion(n_rounds=2) # if using group-based approach
    #    or env.run_until_stable()
    #
    #    But typically we orchestrate chain-of-thought from the Moderator side:

    # We can create a trivial "Task" wrapper to pass to the moderator
    class SimpleTask:
        def __init__(self, question, knowledge):
            self.question = question
            self.knowledge = knowledge
            # if we had choices, we can define self.choices, etc.

    # Prepare the task
    sample_task = SimpleTask(question_str, knowledge_str)

    group = env 

    # We'll call the advanced moderator method
    final_answer, steps = advanced_moderator.o1think(
        task=sample_task,
        knowledges=sample_task.knowledge,
        group=group,
        args=args
    )

    # 7. Print out or log final results
    print("\n=============== FINAL RESULT ===============")
    if final_answer:
        print("Final Answer:\n", final_answer)
    else:
        print("No final answer was produced.")

    print("\n=============== STEP HISTORY ===============")
    if steps:
        for idx, entry in enumerate(steps):
            if isinstance(entry, tuple) and len(entry) >= 2:
                step_label, reasoning = entry[0], entry[1]
                print(f"\n{step_label} \nReasoning:\n{reasoning}")
    else:
        print("No steps to display.")

    print("\n======= Multi-Agent System Execution Complete =======")

if __name__ == "__main__":
    main()
