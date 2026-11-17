# from `gold_with_3_distractors_context_cot_qa_codex.txt`

one_shot_rag_qa_docs = (
    """triplets: ('erik hort', 'born in', 'montebello'), ('erik hort', 'is', 'american'), ('montebello', 'is located in', 'rockland county')"""
)



one_shot_ircot_demo = (
    f'{one_shot_rag_qa_docs}'
    '\n\nQuestion: '
    f"When was Neville A. Stanton's employer founded?"
    '\nThought: '
    f"The employer of Neville A. Stanton is University of Southampton. The University of Southampton was founded in 1862. So the answer is: 1862."
    '\n\n'
)


rag_qa_system = (
    'As an advanced reading comprehension assistant, your task is to carefully analyze triplets and extract useful information from them to answer corresponding questions.'
    'Your response start after "Thought: ", where you will methodically break down the reasoning process, illustrating how you arrive at conclusions. '
    'If the provided information cannot answer the question, output No answer.'
    'Conclude with "Answer: " to present a concise, definitive response, devoid of additional elaborations.'
)

one_shot_rag_qa_input = (
    f"{one_shot_rag_qa_docs}"
    "\n\nQuestion: "
    "What county is Erik Hort's birthplace a part of?"
    '\nThought: '
)

one_shot_rag_qa_output = (
    "The triplet ('erik hort', 'born in', 'montebello') tells us that Erik Hort was born in Montebello. The triplet ('montebello', 'is located in', 'rockland county') tells us that Montebello is located in Rockland County. Therefore, since Erik Hort was born in Montebello and Montebello is in Rockland County, Erik Hort's birthplace is part of Rockland County."
    "\nAnswer: Rockland County."
)


prompt_template = [
    {"role": "system", "content": rag_qa_system},
    {"role": "user", "content": one_shot_rag_qa_input},
    {"role": "assistant", "content": one_shot_rag_qa_output},
    {"role": "user", "content": "${prompt_user}"}
]
