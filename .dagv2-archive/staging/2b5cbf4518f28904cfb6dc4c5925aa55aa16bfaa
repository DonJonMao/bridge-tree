import json
import difflib
from pydantic import BaseModel, Field, TypeAdapter
from openai import OpenAI
from copy import deepcopy
from typing import Union, Optional, List, Dict, Any, Tuple, Literal
import re
import ast
from .prompt.filter_default_prompt_copy import best_dspy_prompt

class Fact(BaseModel):
    fact: list[list[str]] = Field(description="A list of facts, each fact is a list of 3 strings: [subject, predicate, object]")


class DSPyFilter_genedata:
    def __init__(self, hipporag):
        """
        Initializes the object with the necessary configurations and templates for processing input and output messages.

        Parameters:
        hipporag : An object that provides the global configuration and the LLM model required for inference.

        Attributes:
        dspy_file_path : The file path for reranking as specified in the global configuration.
        one_input_template : A string template for formatting the input message with placeholders for specific fields.
        one_output_template : A string template for formatting the output message with specific fields.
        message_template : A template generated using the specified dspy file path.
        llm_infer_fn : A function reference for making inferences using the provided LLM model.
        model_name : The name of the language model as specified in the global configuration.
        default_gen_kwargs : A dictionary for storing the default generation keyword arguments.
        """
        dspy_file_path = hipporag.global_config.rerank_dspy_file_path
        self.one_input_template_yuan = """[[ ## question ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}\n\nRespond with the corresponding output fields, starting with the field `[[ ## fact_after_filter ## ]]` (must be formatted as a valid Python Fact), and then ending with the marker for `[[ ## completed ## ]]`."""
        self.one_output_template_yuan = """[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## completed ## ]]"""
        self.one_input_template_start = """[[ ## query ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
        self.one_input_template = """[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
        self.one_output_template = """[[ ## thought ## ]]\n{thought}\n\n[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## question ## ]]\n{question}"""
        self.message_template = self.make_template(dspy_file_path)
        self.llm_infer_fn = hipporag.llm_model.infer
        self.model_name = hipporag.global_config.llm_name
        self.default_gen_kwargs = {}

    def make_template(self, dspy_file_path):
        if dspy_file_path is not None:
            dspy_saved = json.load(open(dspy_file_path, 'r'))
        else:
            dspy_saved = best_dspy_prompt

        system_prompt = dspy_saved['prog']['system']
        # print(system_prompt)
        # exit(0)
        message_template = [
            {"role": "system", "content": system_prompt},
        ]
        demos = dspy_saved["prog"]["demos"]
        for demo1 in demos:
                for Index,demo in enumerate(demo1):
                    if Index == 0: 
                        message_template.append({"role": "user", "content": self.one_input_template_start.format(question=demo["query"], fact_before_filter=demo["fact_before_filter"])})
                        message_template.append({"role": "assistant", "content": self.one_output_template.format(thought=demo["thought"],fact_after_filter=demo["fact_after_filter"],question=demo["question"])})
                    else:
                        message_template.append({"role": "user", "content": self.one_input_template.format(fact_before_filter=demo["fact_before_filter"])})
                        message_template.append({"role": "assistant", "content": self.one_output_template.format(thought=demo["thought"],fact_after_filter=demo["fact_after_filter"],question=demo["question"])})
        return message_template
    
    def make_template_copy(self, dspy_file_path):
        if dspy_file_path is not None:
            dspy_saved = json.load(open(dspy_file_path, 'r'))
        else:
            dspy_saved = best_dspy_prompt

        system_prompt = dspy_saved['prog']['system']
        # print(system_prompt)
        # exit(0)
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
                    # fields[k] = parse_value(v, signature.output_fields[k].annotation) if _parse_values else v
                    try:
                        parsed_value = json.loads(value)
                    except json.JSONDecodeError:
                        try:
                            parsed_value = ast.literal_eval(value)
                        except (ValueError, SyntaxError):
                            parsed_value = value
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
        # call openai

        self.default_gen_kwargs['max_completion_tokens'] = 1024

        response = self.llm_infer_fn(
            messages=messages,
            model=self.model_name,
            **self.default_gen_kwargs
        )

        # if len(response) > 1:
        #     return response[0]
        return response[0],response[1]

    def __call__(self, *args, **kwargs):
        return self.rerank(*args, **kwargs)

    def rerank(self,
               query: str,
               candidate_items: List[Tuple],
               candidate_indices: List[int],
               old_message: List[Dict[str, str]],
               len_after_rerank: int =None) -> Tuple[List[int], List[Tuple], dict]:
        fact_before_filter = {"fact": [list(candidate_item) for candidate_item in candidate_items]}
        try:
            # prediction = self.program(question=query, fact_before_filter=json.dumps(fact_before_filter))
            response,response1 = self.llm_call(query, json.dumps(fact_before_filter),old_message)
            generated_facts,additonal_query,thought = self.parse_filter(response)   #解析出响应中的三元组
        except Exception as e:
            print('exception', e)
            generated_facts = []
            additonal_query = ''
            thought = ''
            response1={'prompt_tokens':0,'completion_tokens':0}
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
        return sorted_candidate_indices[:len_after_rerank], sorted_candidate_items[:len_after_rerank], {'confidence': None},additonal_query,thought,response1['prompt_tokens'],response1['completion_tokens']