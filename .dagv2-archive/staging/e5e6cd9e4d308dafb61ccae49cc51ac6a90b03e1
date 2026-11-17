# PrefEval Benchmark: Do LLMs Recognize Your Preferences? Evaluating Personalized Preference Following in LLMs



<p align="center">
| <a href="https://prefeval.github.io/"><b>Website</b></a> | <a href="https://arxiv.org/abs/2502.09597"><b>Paper</b></a> | <a href="https://huggingface.co/datasets/siyanzhao/prefeval_explicit"><b>Data</b></a> |
</p>


<p align="center">
  <img src="https://github.com/amazon-science/PrefEval/blob/main/prefeval.png" alt="mainfigure" width="760">
</p>

---

### 🏆Performance Leaderboard on Subset Tasks🏆
*Ranked by performance in the Reminder (10 Turns) column.* 
This table presents the performance results for the topic: Travel-Restaurants. (With explicit preference and generation task)

| Model              | Zero-shot (10 Turns) | **Reminder (10 Turns)** | Zero-shot (300 Turns) | Reminder (300 Turns) |
|--------------------|----------------------|-------------------------|-----------------------|----------------------|
| **o1-preview**      | **0.50**             | **0.98**                | **0.14**              | **0.98**             |
| **GPT-4o**          | 0.07                 | **0.98**                | 0.05                  | 0.23                 |
| **Claude-3-Sonnet** | 0.05                 | 0.96                    | 0.04                  | 0.36                 |
| **Gemini-1.5-Pro**  | 0.07                 | 0.91                    | 0.09                  | 0.05                 |
| **Mistral-8x7B**    | 0.08                 | 0.84                    | -                     | -                    |
| **Mistral-7B**      | 0.03                 | 0.75                    | -                     | -                    |
| **Claude-3-Haiku**  | 0.05                 | 0.68                    | 0.02                  | 0.02                 |
| **Llama3-8B**       | 0.00                 | 0.57                    | -                     | -                    |
| **Claude-3.5-Sonnet**| 0.07                | 0.45                    | 0.02                  | 0.02                 |
| **Llama3-70B**      | 0.11                 | 0.37                    | -                     | -                    |

---






### Dataset Location

The preference evaluation dataset is located in the `benchmark_dataset` directory.

### Data Format

The dataset is provided in json format and contains the following attributes:
1. Explicit Preference.
```
{
    "preference": [string] The user's stated preference that the LLM should follow.
    "question": [string] The user's query related to the preference, where a generic response to this question is highly likely to violate the preference.
    "explanation": [string] A 1-sentence explanation of why answering this question in a preference-following way is challenging.
}

```
2. Implicit Preference - Choice-based Conversation
```
{
    "preference": [string] The user's explicit preference that the LLM should follow.
    "question": [string] The user's query related to the preference, where a generic response to this question is highly likely to violate the preference.
    "explanation": [string] A 1-sentence explanation of why answering this question in a preference-following way is challenging.
    "implicit_query": [string] A secondary query that offers further insight into the user’s preference, where the assistant provides multiple options.
    "options": [list] A set of options that the assistant presents in response to the user's implicit query, some of which align with and others that violate the user’s implied preference.
    "conversation": {
        "query": [string] Implicit_Query,
        "assistant_options": [string] The assistant's presenting multiple options, some aligned and some misaligned with the user's preference,
        "user_selection": [string] The user's choice or rejection of certain options.
        "assistant_acknowledgment": [string] The assistant's recognition of the user’s choice.
    },
    "aligned_op": [string] The option that aligns with the user’s preference.
}
```
3. Implicit Preference - Persona-driven Conversation

```
{
    "preference": [string] The user's explicit preference that the LLM should follow.
    "question": [string] The user's query related to the preference, where a generic response to this question is highly likely to violate the preference.
    "explanation": [string] A 1-sentence explanation of why answering this question in a preference-following way is challenging.
    "persona": [string] The assigned persona guiding the conversation, e.g., "a retired postal worker enjoying his golden years.",
    "conversation": {
        "turn1": { "user": [string], "assistant": [string] },
        "turn2": { "user": [string], "assistant": [string] },
        ...,
        "turnN": { "user": [string], "assistant": [string] }
    },
}
```
## Benchmarking on PrefEval

### Environment Setup

Create a conda environment:

```
conda create -n prefeval python=3.10 -y
conda activate prefeval
```

Install the required dependencies:

```
pip install -r requirements.txt
```

Set up AWS credentials for calling Bedrock API.
- Follow the instruction [here](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) to install aws cli.
- Run the following command and enter your aws credentials: `AWS Access Key ID` and `AWS Secret Access Key`
```
aws configure
```

### Example Usages:
The following scripts demonstrate how to benchmark various scenarios. You can flexibly modify the arguments within these scripts to assess different topics, preference styles, and inter-turn conversation numbers to create varying task difficulties.


### Example 1: Benchmark Generation Tasks

```
cd example_scripts
```

1. Benchmark Claude 3 Haiku with zero-shot on explicit preferences, using 3 inter-turns for the travel restaurant topic:
```
bash run_and_eval_explicit.sh
```
3. Benchmark Claude 3 Haiku with zero-shot on implicit preferences, using persona-based preferences and 2 inter-turns:
```
bash run_and_eval_implicit.sh
```

### Example 2: Benchmark Classification Tasks

1. Benchmark classification tasks on all topics with explicit/implicit preferences, using Claude 3 Haiku with zero-shot and 0 inter-turns:
```
bash run_mcq_task.sh
```

### Example 3: Test 5 baselines methods
1. Test 5 baseline methods on explicit preferences: zero-shot, reminder, chain-of-thought, RAG, self-critic.

```
bash run_and_eval_explicit_baselines.sh 
```

Note: All benchmarking results will be saved in the `benchmark_results/` directory.

---

### SFT Code

Code and instructions for SFT (Supervised Fine-Tuning) are located in the `SFT/` directory.

---
### Benchmark preference and query pair generation:
We provides code for generating preference-query pairs. While our final benchmark dataset includes extensive human filtering and iterative labeling, we provide the initial sampling code for reproducibility.

```
cd benchmark_dataset
python claude_generate_preferences_questions.py
```
