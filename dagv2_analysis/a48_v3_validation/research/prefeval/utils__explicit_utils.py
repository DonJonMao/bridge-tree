import os
import json
import time
import random
from .common_utils import COT_PROMPT, REMINDER


def check_file_exists(save_file, total_len):
    if os.path.exists(
        save_file,
    ):
        with open(
            save_file,
            "r",
        ) as infile:
            already_saved_data = json.load(infile)
        if len(already_saved_data) == total_len:
            print(f"Already saved enough data of {total_len}, Skipping evaluation.")
            return True
        else:
            print("only have ", len(already_saved_data))
            return False
    return False


def print_conversation(messages):
    for message in messages:
        role = message["role"]
        content = message["content"]
        print(f"{role.capitalize()}: {content}\n")
        print()


def load_files_explicit(args):
    # system prompt:
    with open(
        f"{args.dir}/benchmark_dataset/explicit_preference/{args.topic}.json",
        "r",
    ) as infile:
        existing_data = json.load(infile)
    dir_path = f"{args.dir}/benchmark_results/explicit/generation_results/{args.task}/{args.topic}/"
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    save_file = f"{args.dir}/benchmark_results/explicit/generation_results/{args.task}/{args.topic}/{args.model}_{args.topic}_{args.inter_turns}interturn.json"
    return existing_data, save_file


def load_files_explicit_selfcritic(args):
    # system prompt:
    with open(
        f"/data/siyanz-sandbox/benchmark_results/explicit/single_pref/{args.topic}/{args.model}_{args.topic}_{args.inter_turns}interturn.json",
        "r",
    ) as infile:
        existing_data = json.load(infile)
    # check if this directory does not exist, create one:
    dir_path = f"/data/siyanz-sandbox/benchmark_results/explicit/{args.task}/{args.topic}/"
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    save_file = f"/data/siyanz-sandbox/benchmark_results/explicit/{args.task}/{args.topic}/{args.model}_{args.topic}_{args.inter_turns}interturn.json"
    return existing_data, save_file


def load_files_explicit_mcq(args):
    # system prompt:
    with open(
        f"/data/siyanz-sandbox/preference_dataset/implicit_preference_benchmark/type_a/{args.topic}.json",
        "r",
    ) as infile:
        existing_data = json.load(infile)
    # check if this directory does not exist, create one:
    dir_path = f"/data/siyanz-sandbox/benchmark_results/explicit/{args.task}/{args.topic}/"
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    save_file = f"/data/siyanz-sandbox/benchmark_results/explicit/{args.task}/{args.topic}/{args.model}_{args.topic}_{args.inter_turns}interturn.json"
    return existing_data, save_file


def extract_conversation_to_messages(conversation, model_type):
    # this is for implicit preference
    messages = []
    role_list = []

    for line in conversation:
        role = line["role"]
        content = line["content"]
        role_list.append(role)

        if model_type == "mistral":
            if role == "user":
                messages.append(f"[INST] {content} [/INST]")
            else:
                messages.append(f"{content}</s>")
        elif model_type == "llama":
            messages.append(f"<|start_header_id|>{role}<|end_header_id|>\n{content}<|eot_id|>")
        elif model_type == "claude":
            messages.append({"role": role, "content": content})
        else:
            raise ValueError(f"Invalid model_type: {model_type}")

    return messages, role_list


def create_user_pref_message(preference, model_type, system_prompt):
    if model_type == "claude":
        user_message = [{"role": "user", "content": preference}]
    elif model_type == "llama":
        user_message = f"""
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt} <|eot_id|><|start_header_id|>user<|end_header_id|>

{preference}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
    elif model_type == "mistral":
        user_message = f"<s>[INST]{system_prompt} {preference} [/INST]"
    elif model_type == "gpt":
        user_message = {"role": "user", "content": str(preference)}
        system_prompt = {
            "role": "system",
            "content": system_prompt,
        }
        # user_message = [system_prompt, user_message]
        user_message = [user_message]
    elif model_type == "gemini":
        return {
            "system_instruction": system_prompt,
            "messages": [
                {"role": "user", "parts": [{"text": preference}]},
            ],
        }
    else:
        raise ValueError(f"Invalid model type: {model_type}")

    return user_message


def get_question_prompt(
    preference,
    pref_generation,
    question,
    multi_inter_message,
    model_type,
    turn_number,
    remind,
    cot,
    args,
    max_tokens,
    system_prompt="You are a helpful asisstant.",
):

    if remind:
        question = question + REMINDER
    if cot:
        question = COT_PROMPT + question
    question += f" (Please respond within {max_tokens} words.)"
    if model_type == "claude":
        user_message = {"role": "user", "content": preference}
        messages = [user_message, {"role": "assistant", "content": pref_generation}]
        if multi_inter_message:
            assert turn_number > 0
            messages.extend(multi_inter_message)
        messages.append({"role": "user", "content": question})
    elif model_type == "llama":
        if multi_inter_message is None:
            assert turn_number <= 0
            multi_inter_message = ""
        messages = f"""<|begin_of_text|>
<|start_header_id|>system<|end_header_id|>
{system_prompt}
<|eot_id|>
<|start_header_id|>user<|end_header_id|>
{preference}
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
{pref_generation}
<|eot_id|>
{multi_inter_message}
<|start_header_id|>user<|end_header_id|>
{question}
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>"""

    elif model_type == "mistral":
        if multi_inter_message is None:
            assert turn_number <= 0
            multi_inter_message = ""
        messages = f"""<s>[INST]
{system_prompt}
{preference}
[/INST]
{pref_generation}</s>
{multi_inter_message}
[INST]
{question}
[/INST]"""

    elif model_type == "gpt":
        user_message = {"role": "user", "content": preference}
        system_prompt = {"role": "system", "content": system_prompt}
        messages = [
            user_message,
            {"role": "assistant", "content": pref_generation},
        ]
        if multi_inter_message:
            assert turn_number > 0
            messages.extend(multi_inter_message)
        messages.append({"role": "user", "content": question})
    elif model_type == "gemini":
        msgs = [
            {"role": "user", "parts": [{"text": preference}]},
            {"role": "model", "parts": [{"text": pref_generation}]},
        ]
        if multi_inter_message:
            msgs.extend(multi_inter_message)
        msgs.append({"role": "user", "parts": [{"text": question}]})

        return {"system_instruction": system_prompt, "messages": msgs}
    else:
        raise ValueError(f"Invalid model type: {model_type}")

    return messages


def get_self_critic_prompt_critic(
    args,
    critic_request,
    preference,
    pref_generation,
    response_to_q,
    multi_inter_message,
    question,
    system_prompt,
):
    if "claude" in args.model:
        critic_messages = [
            {"role": "user", "content": preference},
            {"role": "assistant", "content": pref_generation},
        ]
        if args.inter_turns > 0:
            critic_messages.extend(multi_inter_message)
        critic_messages.extend(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": response_to_q},
            ]
        )
        critic_messages.append({"role": "user", "content": critic_request})
    elif "llama" in args.model:
        if args.inter_turns == 0:
            multi_inter_message = ""
        critic_messages = f"""<|begin_of_text|>
        <|start_header_id|>system<|end_header_id|>
        {system_prompt}
        <|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {preference}
        <|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        {pref_generation}
        <|eot_id|>{multi_inter_message}
        <|start_header_id|>user<|end_header_id|>
        {question}
        <|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        {response_to_q}
        <|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {critic_request}
        <|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        """
    elif "mistral" in args.model:
        critic_messages = f"""<s>[INST]
{system_prompt}
{preference}
[/INST]
{pref_generation}</s>
{multi_inter_message}
[INST]
{question}
[/INST]
{response_to_q}</s>
[INST]
{critic_request}
[/INST]
"""
    return critic_messages


def get_self_critic_prompt_response(
    args,
    critic_request,
    preference,
    pref_generation,
    response_to_q,
    multi_inter_message,
    question,
    critic,
    revision_request,
    system_prompt,
):
    if "claude" in args.model:
        critic_messages = [
            {"role": "user", "content": preference},
            {"role": "assistant", "content": pref_generation},
        ]
        if args.inter_turns > 0:
            critic_messages.extend(multi_inter_message)
        critic_messages.extend(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": response_to_q},
            ]
        )
        critic_messages.append({"role": "user", "content": critic_request})
        critic_messages.append({"role": "assistant", "content": critic})
        critic_messages.append({"role": "user", "content": revision_request})
    elif "llama" in args.model:
        critic_messages = f"""<|begin_of_text|>
        <|start_header_id|>system<|end_header_id|>
        {system_prompt}
        <|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {preference}
        <|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        {pref_generation}
        <|eot_id|>
        {multi_inter_message}
        <|start_header_id|>user<|end_header_id|>
        {question}
        <|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        {response_to_q}
        <|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {critic_request}
        <|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        {critic}
        <|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {revision_request}
        <|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        """
    elif "mistral" in args.model:
        critic_messages = f"""<s>[INST]
{system_prompt}
{preference}
[/INST]
{pref_generation}</s>
{multi_inter_message}
[INST]
{question}
[/INST]
{response_to_q}</s>
[INST]
{critic_request}
[/INST]
{critic}</s>
[INST]
{revision_request}
[/INST]
"""
    return critic_messages


def convert_top_k_sentences_to_msg(top_k_sentences):
    msg = (
        "Before answering my question, please consider the following context from our previous conversations. "
        "These are the 5 most relevant exchanges that we had previously, which may contain information about "
        "my preferences or prior discussions related to my query:\n\n"
        "#Start of Context#\n"
    )
    for idx, sentence in enumerate(top_k_sentences, 1):
        msg += f"exchange {idx}. {sentence}\n"

    msg += (
        "#End of Context#\n\n"
        "Please use this context to inform your answer and adhere to any preferences I've expressed "
        "that are relevant to the current query. Note that not all contexts are useful for answering "
        "my question and there may be no context that is useful. Now, please address my question:\n\n"
    )
    return msg


def get_question_prompt_rag(
    preference,
    pref_generation,
    question,
    multi_inter_message,
    model_type,
    turn_number,
    top_k_sentences,
    max_tokens,
    system_prompt="You are a helpful asisstant.",
):
    top_k_msg = convert_top_k_sentences_to_msg(top_k_sentences)
    question = top_k_msg + question
    question += f" (Please respond within {max_tokens} words.)"
    if model_type == "claude":
        user_message = {"role": "user", "content": preference}
        messages = [user_message, {"role": "assistant", "content": pref_generation}]
        if multi_inter_message:
            assert turn_number > 0
            messages.extend(multi_inter_message)
        messages.append({"role": "user", "content": question})
    elif model_type == "llama":
        if multi_inter_message is None:
            assert turn_number <= 0
            multi_inter_message = ""
        messages = f"""<|begin_of_text|>
<|start_header_id|>system<|end_header_id|>
{system_prompt}
<|eot_id|>
<|start_header_id|>user<|end_header_id|>
{preference}
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
{pref_generation}
<|eot_id|>
{multi_inter_message}
<|start_header_id|>user<|end_header_id|>
{question}
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>"""
    elif model_type == "mistral":
        if multi_inter_message is None:
            assert turn_number <= 0
            multi_inter_message = ""
        messages = f"""<s>[INST]
{system_prompt}
{preference}
[/INST]
{pref_generation}</s>
{multi_inter_message}
[INST]
{question}
[/INST]"""
    elif model_type == "gpt":
        user_message = {"role": "user", "content": preference}
        system_prompt = {"role": "system", "content": system_prompt}
        messages = [
            system_prompt,
            user_message,
            {"role": "assistant", "content": pref_generation},
        ]
        if multi_inter_message:
            assert turn_number > 0
            messages.extend(multi_inter_message)
        messages.append({"role": "user", "content": question})
    else:
        raise ValueError(f"Invalid model type: {model_type}")

    return messages
