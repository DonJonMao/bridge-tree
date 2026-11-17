import json
import difflib
from pydantic import BaseModel, Field, TypeAdapter
from openai import OpenAI
from copy import deepcopy
from typing import Union, Optional, List, Dict, Any, Tuple, Literal
import re
import ast
from .prompt.filter_default_prompt_copy import best_dspy_prompt

from src.cirag.models import (
    VLLMServerModel
)
class Fact(BaseModel):
    fact: list[list[str]] = Field(description="A list of facts, each fact is a list of 3 strings: [subject, predicate, object]")


class DSPyFilter_genedata_sllm:
    def __init__(self, cirag):
        dspy_file_path = cirag.global_config.rerank_dspy_file_path
        self.one_input_template_yuan = """[[ ## question ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}\n\nRespond with the corresponding output fields, starting with the field `[[ ## fact_after_filter ## ]]` (must be formatted as a valid Python Fact), and then ending with the marker for `[[ ## completed ## ]]`."""
        self.one_output_template_yuan = """[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## completed ## ]]"""
        self.one_input_template_start = """[[ ## query ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
        self.one_input_template = """[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
        self.one_output_template = """[[ ## thought ## ]]\n{thought}\n\n[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## question ## ]]\n{question}"""
        self.message_template = self.make_template(dspy_file_path)
        if cirag.global_config.ab == 'FT':
            model = cirag.llm_model
        else:
            model = VLLMServerModel(
            model_id="Qwen/Qwen2.5-7B-Instruct",
            api_base="http://0.0.0.0:8001/v1",
            api_key="REDACTED_LOCAL_CREDENTIAL",
            lora_name="finetune",
            max_tokens=1024
            )
        self.llm_infer_fn = model
        self.model_name = cirag.global_config.llm_name
        self.default_gen_kwargs = {}

    def make_template(self, dspy_file_path):
        if dspy_file_path is not None:
            dspy_saved = json.load(open(dspy_file_path, 'r'))
        else:
            dspy_saved = best_dspy_prompt

        system_prompt = dspy_saved['prog']['system']
        message_template = [
            {"role": "system", "content": system_prompt},
        ]

        return message_template
    
    def make_template_copy(self, dspy_file_path):
        if dspy_file_path is not None:
            dspy_saved = json.load(open(dspy_file_path, 'r'))
        else:
            dspy_saved = best_dspy_prompt

        system_prompt = dspy_saved['prog']['system']
        message_template = [
            {"role": "system", "content": system_prompt},
        ]
        demos = dspy_saved["prog"]["demos"]
        for demo in demos:
            message_template.append({"role": "user", "content": self.one_input_template.format(question=demo["question"], fact_before_filter=demo["fact_before_filter"])})
            message_template.append({"role": "assistant", "content": self.one_output_template.format(fact_after_filter=demo["fact_after_filter"],additional_information=demo["additional_information"])})
        return message_template

    def parse_filter(self, response):
        sections = [(None, [])]
        field_header_pattern = re.compile('\\[\\[ ## (\\w+) ## \\]\\]')
        for line in response.splitlines():
            match = field_header_pattern.match(line.strip())
            if match:
                sections.append((match.group(1), []))
            else:
                sections[-1][1].append(line)

        sections = [(k, "\n".join(v).strip()) for k, v in sections]
        parsed = []
        parsed1 = ''
        parsed2 = ''
        for k, value in sections:
            if k == "fact_after_filter":
                try:
                    data = ast.literal_eval(value)
                    parsed_value = {"fact": [list(t) for t in data]}
                    parsed = TypeAdapter(Fact).validate_python(parsed_value).fact
                except Exception as e:
                    print(
                        f"Error parsing field {k}: {e}.\n\n\t\tOn attempting to parse the value\n```\n{value}\n```"
                    )
            if k == "question":
                parsed1 = value
            if k == "thought":
                parsed2 = value


        return parsed,parsed1,parsed2

    def llm_call(self, question, fact_before_filter,old_message):
        # make prompt
        messages = deepcopy(self.message_template)
        if old_message:
            messages.extend(old_message)
            messages.append({"role": "user", "content": self.one_input_template.format(fact_before_filter=fact_before_filter)})
        else:
            messages.append({"role": "user", "content": self.one_input_template_start.format(question=question, fact_before_filter=fact_before_filter)})

        self.default_gen_kwargs['max_completion_tokens'] = 1024

        response,input_token_count,output_token_count = self.llm_infer_fn(
            messages=messages
        )
        return response.content,input_token_count,output_token_count

    def __call__(self, *args, **kwargs):
        return self.rerank(*args, **kwargs)

    def rerank(self,
               query: str,
               candidate_items: List[Tuple],
               candidate_indices: List[int],
               old_message: List[Dict[str, str]],
               len_after_rerank: int =None) -> Tuple[List[int], List[Tuple], dict]:
        fact_before_filter = candidate_items
        try:
            response,input_token_count,output_token_count = self.llm_call(query, str(fact_before_filter),old_message)
            generated_facts,additonal_query,thought = self.parse_filter(response)   #解析出响应中的三元组
        except Exception as e:
            print('exception', e)
            generated_facts = []
            additonal_query = ''
            thought = ''
        result_indices = []
        for generated_fact in generated_facts:

            closest_matched_fact = difflib.get_close_matches(str(generated_fact), [str(i) for i in candidate_items], n=1, cutoff=0.0)
            if closest_matched_fact:
                closest_matched_fact = closest_matched_fact[0]
                try:
                    result_indices.append(candidate_items.index(eval(closest_matched_fact)))
                except Exception as e:
                    print('result_indices exception', e)

        sorted_candidate_indices = [candidate_indices[i] for i in result_indices]
        sorted_candidate_items = [candidate_items[i] for i in result_indices]
        return sorted_candidate_indices[:len_after_rerank], sorted_candidate_items[:len_after_rerank], {'confidence': None},additonal_query,thought,input_token_count,output_token_count