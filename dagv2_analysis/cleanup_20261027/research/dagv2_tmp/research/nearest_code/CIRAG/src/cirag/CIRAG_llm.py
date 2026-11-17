import json
import os
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Union, Optional, List, Set, Dict, Any, Tuple, Literal
import numpy as np
import importlib
from collections import defaultdict
from transformers import HfArgumentParser
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from igraph import Graph
import igraph as ig
import numpy as np
from collections import defaultdict
import re
import time
from .llm import _get_llm_class, BaseLLM
from .embedding_model import _get_embedding_model_class, BaseEmbeddingModel
from .embedding_store import EmbeddingStore
from .information_extraction import OpenIE
from .information_extraction.openie_vllm_offline import VLLMOfflineOpenIE
from .evaluation.retrieval_eval import RetrievalRecall
from .evaluation.qa_eval import QAExactMatch, QAF1Score
from .prompt.linking import get_query_instruction
from .prompt.prompt_template_manager import PromptTemplateManager
from .rerank import DSPyFilter
from .rerank_genedata import DSPyFilter_genedata
from .rerank_genedata_sllm import DSPyFilter_genedata_sllm
from .utils.misc_utils import *
from .utils.embed_utils import retrieve_knn
from .utils.typing import Triple
from .utils.config_utils import BaseConfig
import difflib
import ast

from .utils.prompt import *
import copy

from typing import get_type_hints
from src.cirag.models import (
    VLLMServerModel
)


logger = logging.getLogger(__name__)

class LLMAgent_copy:
    def __init__(self, name: str, prompt: str, llm: BaseLLM, response_format: dict = None, _log=True):
        self.name = name
        self.prompt = prompt
        # self.llm = llm
        self.llm = llm
        self.response_format = response_format
        self.log = _log
    def arun1(self, id, placeholder: dict, openai_params: dict = None):
        messages = copy.deepcopy(self.prompt)
        # print(placeholder)
        messages[-1]["content"] = messages[-1]["content"].format(
            knowledge=placeholder["knowledge"],
            question=placeholder["question"],
            thought=placeholder["thought"],
            known_entity=placeholder["known_entity"]
        )
        print("(messages)")
        print(messages)
        # print(messages)
        rsp = self.llm.infer(
            messages=messages,
            # response_format=self.response_format,
        )
        # print(rsp)
        return rsp[0]
    def arun(self, id, placeholder: dict, openai_params: dict = None):
        messages = [
            {"role": "user", "content": self.prompt.format_map(placeholder)},
        ]
        rsp = self.llm.infer(
            messages=messages,
            response_format=self.response_format,
        )
        return rsp[0]

class CIRAG:

    def __init__(self,
                 global_config=None,
                 save_dir=None,
                 llm_model_name=None,
                 llm_base_url=None,
                 embedding_model_name=None,
                 embedding_base_url=None,
                 azure_endpoint=None,
                 azure_embedding_endpoint=None):
        """
        Initializes an instance of the class and its related components.

        Attributes:
            global_config (BaseConfig): The global configuration settings for the instance. An instance
                of BaseConfig is used if no value is provided.
            saving_dir (str): The directory where specific CIRAG instances will be stored. This defaults
                to `outputs` if no value is provided.
            llm_model (BaseLLM): The language model used for processing based on the global
                configuration settings.
            openie (Union[OpenIE, VLLMOfflineOpenIE]): The Open Information Extraction module
                configured in either online or offline mode based on the global settings.
            graph: The graph instance initialized by the `initialize_graph` method.
            embedding_model (BaseEmbeddingModel): The embedding model associated with the current
                configuration.
            chunk_embedding_store (EmbeddingStore): The embedding store handling chunk embeddings.
            entity_embedding_store (EmbeddingStore): The embedding store handling entity embeddings.
            fact_embedding_store (EmbeddingStore): The embedding store handling fact embeddings.
            prompt_template_manager (PromptTemplateManager): The manager for handling prompt templates
                and roles mappings.
            openie_results_path (str): The file path for storing Open Information Extraction results
                based on the dataset and LLM name in the global configuration.
            rerank_filter (Optional[DSPyFilter]): The filter responsible for reranking information
                when a rerank file path is specified in the global configuration.
            ready_to_retrieve (bool): A flag indicating whether the system is ready for retrieval
                operations.

        Parameters:
            global_config: The global configuration object. Defaults to None, leading to initialization
                of a new BaseConfig object.
            working_dir: The directory for storing working files. Defaults to None, constructing a default
                directory based on the class name and timestamp.
            llm_model_name: LLM model name, can be inserted directly as well as through configuration file.
            embedding_model_name: Embedding model name, can be inserted directly as well as through configuration file.
            llm_base_url: LLM URL for a deployed LLM model, can be inserted directly as well as through configuration file.
        """
        if global_config is None:
            self.global_config = BaseConfig()
        else:
            self.global_config = global_config

        #Overwriting Configuration if Specified
        if save_dir is not None:
            self.global_config.save_dir = save_dir

        if llm_model_name is not None:
            self.global_config.llm_name = llm_model_name

        if embedding_model_name is not None:
            self.global_config.embedding_model_name = embedding_model_name

        if llm_base_url is not None:
            self.global_config.llm_base_url = llm_base_url

        if embedding_base_url is not None:
            self.global_config.embedding_base_url = embedding_base_url

        if azure_endpoint is not None:
            self.global_config.azure_endpoint = azure_endpoint

        if azure_embedding_endpoint is not None:
            self.global_config.azure_embedding_endpoint = azure_embedding_endpoint

        _print_config = ",\n  ".join([f"{k} = {v}" for k, v in asdict(self.global_config).items()])
        logger.debug(f"CIRAG init with config:\n  {_print_config}\n")

        #LLM and embedding model specific working directories are created under every specified saving directories
        llm_label = self.global_config.llm_name.replace("/", "_")
        embedding_label = self.global_config.embedding_model_name.replace("/", "_")
        self.working_dir = os.path.join(self.global_config.save_dir, f"{llm_label}_{embedding_label}")

        if not os.path.exists(self.working_dir):
            logger.info(f"Creating working directory: {self.working_dir}")
            os.makedirs(self.working_dir, exist_ok=True)

        self.llm_model: BaseLLM = _get_llm_class(self.global_config)

        self.reanswer1 = LLMAgent_copy("reanswer", extract_answer_prompt_copy, self.llm_model)
        self.reanswer = LLMAgent_copy("reanswer", extract_answer_prompt, self.llm_model)

        if self.global_config.openie_mode == 'online':
            self.openie = OpenIE(llm_model=self.llm_model)        #封装LLM以及ner和三元组抽取
        elif self.global_config.openie_mode == 'offline':
            self.openie = VLLMOfflineOpenIE(self.global_config)

        self.graph = self.initialize_graph()

        if self.global_config.openie_mode == 'offline':
            self.embedding_model = None
        else:
            self.embedding_model: BaseEmbeddingModel = _get_embedding_model_class(
                embedding_model_name=self.global_config.embedding_model_name)(global_config=self.global_config,
                                                                              embedding_model_name=self.global_config.embedding_model_name)
        self.chunk_embedding_store = EmbeddingStore(self.embedding_model,
                                                    os.path.join(self.working_dir, "chunk_embeddings"),
                                                    self.global_config.embedding_batch_size, 'chunk')
        self.entity_embedding_store = EmbeddingStore(self.embedding_model,
                                                     os.path.join(self.working_dir, "entity_embeddings"),
                                                     self.global_config.embedding_batch_size, 'entity')
        self.fact_embedding_store = EmbeddingStore(self.embedding_model,
                                                   os.path.join(self.working_dir, "fact_embeddings"),
                                                   self.global_config.embedding_batch_size, 'fact')

        self.prompt_template_manager = PromptTemplateManager(role_mapping={"system": "system", "user": "user", "assistant": "assistant"})
        self.openie_results_path = os.path.join(self.global_config.save_dir,f'openie_results_ner_{self.global_config.llm_name.replace("/", "_")}.json')
        self.rerank_filter_gene_data = DSPyFilter_genedata(self)
        self.ready_to_retrieve = False

        self.ppr_time = 0
        self.rerank_time = 0
        self.all_retrieval_time = 0
        self.retrieve_input_token_count = 0
        self.retrieve_output_token_count = 0
        self.qa_input_token_count = 0
        self.qa_output_token_count = 0

        self.ent_node_to_chunk_ids = None


    def initialize_graph(self):
        """
        Initializes a graph using a Pickle file if available or creates a new graph.

        The function attempts to load a pre-existing graph stored in a Pickle file. If the file
        is not present or the graph needs to be created from scratch, it initializes a new directed
        or undirected graph based on the global configuration. If the graph is loaded successfully
        from the file, pertinent information about the graph (number of nodes and edges) is logged.

        Returns:
            ig.Graph: A pre-loaded or newly initialized graph.

        Raises:
            None
        """
        self._graph_pickle_filename = os.path.join(
            self.working_dir, f"graph.pickle"
        )

        preloaded_graph = None

        if not self.global_config.force_index_from_scratch:
            if os.path.exists(self._graph_pickle_filename):
                preloaded_graph = ig.Graph.Read_Pickle(self._graph_pickle_filename)

        if preloaded_graph is None:
            return ig.Graph(directed=self.global_config.is_directed_graph)
        else:
            logger.info(
                f"Loaded graph from {self._graph_pickle_filename} with {preloaded_graph.vcount()} nodes, {preloaded_graph.ecount()} edges"
            )
            return preloaded_graph

    def pre_openie(self,  docs: List[str]):
        logger.info(f"Indexing Documents")
        logger.info(f"Performing OpenIE Offline")

        chunks = self.chunk_embedding_store.get_missing_string_hash_ids(docs)

        all_openie_info, chunk_keys_to_process = self.load_existing_openie(chunks.keys())
        new_openie_rows = {k : chunks[k] for k in chunk_keys_to_process}

        if len(chunk_keys_to_process) > 0:
            new_ner_results_dict, new_triple_results_dict = self.openie.batch_openie(new_openie_rows)
            self.merge_openie_results(all_openie_info, new_openie_rows, new_ner_results_dict, new_triple_results_dict)

        if self.global_config.save_openie:
            self.save_openie_results(all_openie_info)

        assert False, logger.info('Done with OpenIE, run online indexing for future retrieval.')

    def index(self, docs: List[str]):
        """
        Indexes the given documents based on the CIRAG framework which generates an OpenIE knowledge graph
        based on the given documents and encodes passages, entities and facts separately for later retrieval.

        Parameters:
            docs : List[str]
                A list of documents to be indexed.
        """

        logger.info(f"Indexing Documents")

        logger.info(f"Performing OpenIE")

        if self.global_config.openie_mode == 'offline':
            self.pre_openie(docs)

        self.chunk_embedding_store.insert_strings(docs)
        chunk_to_rows = self.chunk_embedding_store.get_all_id_to_rows()


        all_openie_info, chunk_keys_to_process = self.load_existing_openie(chunk_to_rows.keys())

        new_openie_rows = {k : chunk_to_rows[k] for k in chunk_keys_to_process}

        if len(chunk_keys_to_process) > 0:
            new_ner_results_dict, new_triple_results_dict = self.openie.batch_openie(new_openie_rows)
            self.merge_openie_results(all_openie_info, new_openie_rows, new_ner_results_dict, new_triple_results_dict)

        if self.global_config.save_openie:
            self.save_openie_results(all_openie_info)

        ner_results_dict, triple_results_dict = reformat_openie_results(all_openie_info)

        assert len(chunk_to_rows) == len(ner_results_dict) == len(triple_results_dict)

        # prepare data_store
        chunk_ids = list(chunk_to_rows.keys())  #{ h: {"hash_id": h, "content": t} }

        chunk_triples = [[text_processing(t) for t in triple_results_dict[chunk_id].triples] for chunk_id in chunk_ids]
        entity_nodes, chunk_triple_entities = extract_entity_nodes(chunk_triples)
        facts = flatten_facts(chunk_triples)

        logger.info(f"Encoding Entities")
        self.entity_embedding_store.insert_strings(entity_nodes)

        logger.info(f"Encoding Facts")
        self.fact_embedding_store.insert_strings([str(fact) for fact in facts])

        logger.info(f"Constructing Graph")

        self.node_to_node_stats = {}    #实体到实体的图    {（node_key, node_2_key），1}，{（chunk_key, node_key），1}，{(node_key, nn)，score}
        self.ent_node_to_chunk_ids = {}   #实体到文本块的图 {（node_key, chunk_key），1}
        self.fact_to_chunk_ids = {}
        self.fact_to_sentence_ids = {}

        self.add_fact_edges(chunk_ids, chunk_triples)     #添加node_to_node_stats ent_node_to_chunk_ids
        self.add_fact(chunk_ids, chunk_triples)       ##注意这个
        self.add_sentence(chunk_ids, chunk_triples)       ##注意这个
        num_new_chunks = self.add_passage_edges(chunk_ids, chunk_triple_entities)

        if num_new_chunks > 0:
            logger.info(f"Found {num_new_chunks} new chunks to save into graph.")
            self.add_synonymy_edges()

            self.augment_graph()
            self.save_igraph()

    def delete(self, docs_to_delete: List[str]):
        """
        Deletes the given documents from all data structures within the CIRAG class.
        Note that triples and entities which are indexed from chunks that are not being removed will not be removed.

        Parameters:
            docs : List[str]
                A list of documents to be deleted.
        """

        #Making sure that all the necessary structures have been built.
        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()

        current_docs = set(self.chunk_embedding_store.get_all_texts())
        docs_to_delete = [doc for doc in docs_to_delete if doc in current_docs]

        #Get ids for chunks to delete
        chunk_ids_to_delete = set(
            [self.chunk_embedding_store.text_to_hash_id[chunk] for chunk in docs_to_delete])

        #Find triples in chunks to delete
        all_openie_info, chunk_keys_to_process = self.load_existing_openie([])
        triples_to_delete = []

        all_openie_info_with_deletes = []

        for openie_doc in all_openie_info:
            if openie_doc['idx'] in chunk_ids_to_delete:
                triples_to_delete.append(openie_doc['extracted_triples'])
            else:
                all_openie_info_with_deletes.append(openie_doc)

        triples_to_delete = flatten_facts(triples_to_delete)

        #Filter out triples that appear in unaltered chunks
        true_triples_to_delete = []

        for triple in triples_to_delete:
            proc_triple = tuple(text_processing(list(triple)))

            doc_ids = self.proc_triples_to_docs[str(proc_triple)]

            non_deleted_docs = doc_ids.difference(chunk_ids_to_delete)

            if len(non_deleted_docs) == 0:
                true_triples_to_delete.append(triple)

        processed_true_triples_to_delete = [[text_processing(list(triple)) for triple in true_triples_to_delete]]
        entities_to_delete, _ = extract_entity_nodes(processed_true_triples_to_delete)
        processed_true_triples_to_delete = flatten_facts(processed_true_triples_to_delete)

        triple_ids_to_delete = set([self.fact_embedding_store.text_to_hash_id[str(triple)] for triple in processed_true_triples_to_delete])

        #Filter out entities that appear in unaltered chunks
        ent_ids_to_delete = [self.entity_embedding_store.text_to_hash_id[ent] for ent in entities_to_delete]

        filtered_ent_ids_to_delete = []

        for ent_node in ent_ids_to_delete:
            doc_ids = self.ent_node_to_chunk_ids[ent_node]

            non_deleted_docs = doc_ids.difference(chunk_ids_to_delete)

            if len(non_deleted_docs) == 0:
                filtered_ent_ids_to_delete.append(ent_node)

        logger.info(f"Deleting {len(chunk_ids_to_delete)} Chunks")
        logger.info(f"Deleting {len(triple_ids_to_delete)} Triples")
        logger.info(f"Deleting {len(filtered_ent_ids_to_delete)} Entities")

        self.save_openie_results(all_openie_info_with_deletes)

        self.entity_embedding_store.delete(filtered_ent_ids_to_delete)
        self.fact_embedding_store.delete(triple_ids_to_delete)
        self.chunk_embedding_store.delete(chunk_ids_to_delete)

        #Delete Nodes from Graph
        self.graph.delete_vertices(list(filtered_ent_ids_to_delete) + list(chunk_ids_to_delete))
        self.save_igraph()

        self.ready_to_retrieve = False

    def retrieve_copy_ab_FT(self,
                 queries: List[str],
                 num_to_retrieve: int = None,
                 gold_docs: List[List[str]] = None,
               result: Dict[int, List[str]] = None,
               result1: Dict[int, List[str]] = None,
               dataset:str = None) -> List[QuerySolution] | Tuple[List[QuerySolution], Dict]:
        """
        Performs retrieval using the CIRAG framework, which consists of several steps:
        - Fact Retrieval
        - Recognition Memory for improved fact selection
        - Dense passage scoring
        - Personalized PageRank based re-ranking

        Parameters:
            queries: List[str]
                A list of query strings for which documents are to be retrieved.
            num_to_retrieve: int, optional
                The maximum number of documents to retrieve for each query. If not specified, defaults to
                the `retrieval_top_k` value defined in the global configuration.
            gold_docs: List[List[str]], optional
                A list of lists containing gold-standard documents corresponding to each query. Required
                if retrieval performance evaluation is enabled (`do_eval_retrieval` in global configuration).

        Returns:
            List[QuerySolution] or (List[QuerySolution], Dict)
                If retrieval performance evaluation is not enabled, returns a list of QuerySolution objects, each containing
                the retrieved documents and their scores for the corresponding query. If evaluation is enabled, also returns
                a dictionary containing the evaluation metrics computed over the retrieved results.

        Notes
        -----
        - Long queries with no relevant facts after reranking will default to results from dense passage retrieval.
        """
        retrieve_start_time = time.time()  # Record start time

        if num_to_retrieve is None:
            num_to_retrieve = self.global_config.retrieval_top_k

        if gold_docs is not None:
            retrieval_recall_evaluator = RetrievalRecall(global_config=self.global_config)

        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()

        self.get_query_embeddings(queries)

        retrieval_results = []
        logg = []
        rere = 0
        for q_idx, query in tqdm(enumerate(queries), desc="Retrieving", total=len(queries)):
            rerank_start = time.time()
            query1 = query
            top_k_facts_new = []

            newlog = {}
            newlog["question"] = query1
            # print("------------------------------------------")
            # print(query)
            paragraphs = result[q_idx]
            tittles = result1[q_idx]
            cnttt = 0
            while query1 != '<no question>' and cnttt < 4:
                cnttt+=1
                query_fact_scores = self.get_fact_scores(query1)
                sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(query1)
                top_k_docs = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:10]]
                top_k_fact_indices, top_k_facts, rerank_log, addtional_query= self.rerank_facts_copy_new(query, query_fact_scores,top_k_docs,tittles)#三元组在数据库中的位置，三元组

                rerank_end = time.time()
                newlog.setdefault("new_questions", []).append(addtional_query)
                newlog.setdefault("rerank_log", []).append(rerank_log)

                self.rerank_time += rerank_end - rerank_start
                # top_k_docs = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:num_to_retrieve]]
                # print("第"+str(i)+"次循环")
                # print("相似度排序：")
                # print(rerank_log['facts_before_rerank'])
                for j in top_k_facts:
                    if j not in top_k_facts_new:
                        top_k_facts_new.append(j)
                # print("模型过滤后：")
                # print(top_k_facts_new)
                # print("query1：")
                query1 = addtional_query
                # print(query1)
            # print("+++++++++++++++++++++++++++++")
            # print("top_k_facts_new")
            # print(top_k_facts_new)
            top_k_docs_new = []
            for k_fact in top_k_facts_new:
                words = []
                k_factt = tuple(k_fact)
                fact_key = compute_mdhash_id(content=str(k_factt), prefix=("fact-"))
                passages_ids = self.fact_to_chunk_ids[fact_key]
                paragraphs = self.chunk_embedding_store.get_rows(passages_ids)
                passss = [paragraphs[rr]['content'] for  rr in passages_ids]
                for word in k_fact:
                    word1 = word.split()
                    words.append(word1)
                for inde,paragraph in enumerate(passss):
                    # 按换行符分割并去除每部分前后空格
                    parts = [part.strip() for part in paragraph.split('\n')]

                    # 保留第一部分，将剩余部分连接起来
                    tittl = parts[0]
                    paragraph_1 = ' '.join(parts[1:])
                    # paragraphs_new = paragraph.lower().split('.')
                    sentences = [s.strip() + '.' for s in paragraph_1.lower().split('.') if s.strip()]
                    zzw = 0
                    for sentence in sentences:  
                        scen = tittl.lower()+sentence
                        flag = 0
                        for zz in words:
                            cnt = 0
                            total_cnt =  len(zz)
                            for zy in zz:
                                if zy in scen:
                                    cnt+=1
                            if cnt==total_cnt:
                                flag+=1
                        if flag >=2:
                            if tittl.lower()+'\n'+sentence not in top_k_docs_new:
                                top_k_docs_new.append(tittl.lower()+'\n'+sentence)
                            zzw = 1
                    if zzw != 1:
                        if str(k_factt) not in top_k_docs_new:
                            top_k_docs_new.append(str(k_factt))
                            
                            # break
            # newlog["top_k_facts"] = top_k_facts_new
            newlog["sentences"] = top_k_docs_new
            logg.append(newlog)

            # print("____________________________")
            # print("top_k_docs_new")
            # print(top_k_docs_new)
            # rere+=1
            # if rere == 15:
            #     with open("data_15_test.json", "w", encoding="utf-8") as f:
            #         json.dump(logg, f, indent=None, ensure_ascii=False)
            #     exit(0)
            # retrieval_results.append(QuerySolution(question=query, docs=top_k_facts_new))###源代码
            retrieval_results.append(QuerySolution(question=query, docs=top_k_docs_new))
        retrieve_end_time = time.time()  # Record end time
        with open("data_hotpot_qwen7b_lora_1000_1.json", "w", encoding="utf-8") as f:
            json.dump(logg, f, indent=4, ensure_ascii=False)
        self.all_retrieval_time += retrieve_end_time - retrieve_start_time

        logger.info(f"Total Retrieval Time {self.all_retrieval_time:.2f}s")
        logger.info(f"Total Recognition Memory Time {self.rerank_time:.2f}s")
        logger.info(f"Total PPR Time {self.ppr_time:.2f}s")
        logger.info(f"Total Misc Time {self.all_retrieval_time - (self.rerank_time + self.ppr_time):.2f}s")

        # Evaluate retrieval
        # if gold_docs is not None:
        #     k_list = [1, 2, 5, 10, 20, 30, 50, 100, 150, 200]
        #     overall_retrieval_result, example_retrieval_results = retrieval_recall_evaluator.calculate_metric_scores(gold_docs=gold_docs, retrieved_docs=[retrieval_result.docs for retrieval_result in retrieval_results], k_list=k_list)
        #     logger.info(f"Evaluation results for retrieval: {overall_retrieval_result}")

        #     return retrieval_results, overall_retrieval_result
        # else:
        return retrieval_results
    
    def generate_data_retri(self,
                 queries: List[str],
                 num_to_retrieve: int = None,
                 gold_docs: List[List[str]] = None,
               result: Dict[int, List[str]] = None,
               result1: Dict[int, List[str]] = None,
               dataset:str = None) -> List[QuerySolution] | Tuple[List[QuerySolution], Dict]:
         # Record start time

        if num_to_retrieve is None:
            num_to_retrieve = self.global_config.retrieval_top_k

        if gold_docs is not None:
            retrieval_recall_evaluator = RetrievalRecall(global_config=self.global_config)

        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()
        self.get_query_embeddings(queries)
        retrieval_results = []
        logg = []
        rere = 0
        retrieve_start_time = time.time() 
        for q_idx, query in tqdm(enumerate(queries), desc="Retrieving", total=len(queries)):
            query1 = query
            top_k_facts_new = []

            newlog = {}
            newlog["question"] = query1
            paragraphs = result[q_idx]
            tittles = result1[q_idx]
            cnttt = 0
            one_input_template_start = """[[ ## query ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_input_template = """[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_output_template = """[[ ## thought ## ]]\n{thought}\n\n[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## question ## ]]\n{question}"""
            old_message = []
            while query1 != '<no question>' and cnttt < self.global_config.it:
                cnttt+=1
                query_fact_scores = self.get_fact_scores(query1)
                sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(query1)
                top_k_docs = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:10]]
                top_k_fact_indices, top_k_facts, rerank_log, addtional_query,input_token_count,output_token_count= self.rerank_facts_gene_data_retri(query, query_fact_scores,top_k_docs,tittles,old_message,top_k_facts_new)#三元组在数据库中的位置，三元组
                if cnttt == 1:
                    old_message.append({"role": "user", "content": one_input_template_start.format(question=query1, fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                else:
                    old_message.append({"role": "user", "content": one_input_template.format(fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                newlog.setdefault("new_questions", []).append(addtional_query)
                newlog.setdefault("rerank_log", []).append(rerank_log)

                self.retrieve_input_token_count+=input_token_count
                self.retrieve_output_token_count+=output_token_count
                for j in top_k_facts:
                    if j not in top_k_facts_new:
                        top_k_facts_new.append(j)
                query1 = addtional_query
            top_k_docs_new = []
            for k_fact in top_k_facts_new:
                words = []
                k_factt = tuple(k_fact)
                fact_key = compute_mdhash_id(content=str(k_factt), prefix=("fact-"))
                passages_ids = self.fact_to_chunk_ids[fact_key]
                paragraphs = self.chunk_embedding_store.get_rows(passages_ids)
                passss = [paragraphs[rr]['content'] for  rr in passages_ids]
                for word in k_fact:
                    word1 = word.split()
                    words.append(word1)
                for inde,paragraph in enumerate(passss):
                    parts = [part.strip() for part in paragraph.split('\n')]
                    tittl = parts[0]
                    paragraph_1 = ' '.join(parts[1:])
                    sentences = [s.strip() + '.' for s in paragraph_1.lower().split('.') if s.strip()]
                    zzw = 0
                    for sentence in sentences:  
                        scen = tittl.lower()+sentence
                        flag = 0
                        for zz in words:
                            cnt = 0
                            total_cnt =  len(zz)
                            for zy in zz:
                                if zy in scen:
                                    cnt+=1
                            if cnt==total_cnt:
                                flag+=1
                        if flag >=2:
                            if tittl.lower()+'\n'+sentence not in top_k_docs_new:
                                top_k_docs_new.append(tittl.lower()+'\n'+sentence)
                            zzw = 1
                    if zzw != 1:
                        if str(k_factt) not in top_k_docs_new:
                            top_k_docs_new.append(str(k_factt))
                        
            newlog["sentences"] = top_k_docs_new
            newlog["cycle"] = old_message
            logg.append(newlog)
            retrieval_results.append(QuerySolution(question=query, docs=top_k_docs_new,facts=top_k_facts_new))
        retrieve_end_time = time.time()  # Record end time
        filename = f"data_{dataset}_qwen_7b_full_lora_qwen2.5_________100_ab_{self.global_config.ab}_{self.global_config.it}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(logg, f, indent=4, ensure_ascii=False)
        self.all_retrieval_time += retrieve_end_time - retrieve_start_time
        return retrieval_results


    def generate_data(self,
                 queries: List[str],
                 num_to_retrieve: int = None,
                 gold_docs: List[List[str]] = None,
               result: Dict[int, List[str]] = None,
               result1: Dict[int, List[str]] = None,
               dataset:str = None) -> List[QuerySolution] | Tuple[List[QuerySolution], Dict]:
        """
        Performs retrieval using the CIRAG , which consists of several steps:
        - Fact Retrieval
        - Recognition Memory for improved fact selection
        - Dense passage scoring
        - Personalized PageRank based re-ranking

        Parameters:
            queries: List[str]
                A list of query strings for which documents are to be retrieved.
            num_to_retrieve: int, optional
                The maximum number of documents to retrieve for each query. If not specified, defaults to
                the `retrieval_top_k` value defined in the global configuration.
            gold_docs: List[List[str]], optional
                A list of lists containing gold-standard documents corresponding to each query. Required
                if retrieval performance evaluation is enabled (`do_eval_retrieval` in global configuration).

        Returns:
            List[QuerySolution] or (List[QuerySolution], Dict)
                If retrieval performance evaluation is not enabled, returns a list of QuerySolution objects, each containing
                the retrieved documents and their scores for the corresponding query. If evaluation is enabled, also returns
                a dictionary containing the evaluation metrics computed over the retrieved results.

        Notes
        -----
        - Long queries with no relevant facts after reranking will default to results from dense passage retrieval.
        """
         # Record start time

        if num_to_retrieve is None:
            num_to_retrieve = self.global_config.retrieval_top_k

        if gold_docs is not None:
            retrieval_recall_evaluator = RetrievalRecall(global_config=self.global_config)

        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()
        self.get_query_embeddings(queries)
        retrieval_results = []
        logg = []
        rere = 0
        retrieve_start_time = time.time() 
        for q_idx, query in tqdm(enumerate(queries), desc="Retrieving", total=len(queries)):
            query1 = query
            top_k_facts_new = []

            newlog = {}
            newlog["question"] = query1
            # print("------------------------------------------")
            # print(query)
            paragraphs = result[q_idx]
            tittles = result1[q_idx]
            cnttt = 0
            one_input_template_start = """[[ ## query ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_input_template = """[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_output_template = """[[ ## thought ## ]]\n{thought}\n\n[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## question ## ]]\n{question}"""
            old_message = []
            while query1 != '<no question>' and cnttt < self.global_config.it:
                cnttt+=1
                query_fact_scores = self.get_fact_scores(query1)
                sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(query1)
                top_k_docs = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:10]]
                # print(query_fact_scores)
                # exit(0)
                top_k_fact_indices, top_k_facts, rerank_log, addtional_query,input_token_count,output_token_count= self.rerank_facts_gene_data(query, query_fact_scores,top_k_docs,tittles,old_message,top_k_facts_new)#三元组在数据库中的位置，三元组
                if cnttt == 1:
                    old_message.append({"role": "user", "content": one_input_template_start.format(question=query1, fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                else:
                    old_message.append({"role": "user", "content": one_input_template.format(fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                newlog.setdefault("new_questions", []).append(addtional_query)
                newlog.setdefault("rerank_log", []).append(rerank_log)

                self.retrieve_input_token_count+=input_token_count
                self.retrieve_output_token_count+=output_token_count

                for j in top_k_facts:
                    if j not in top_k_facts_new:
                        top_k_facts_new.append(j)
                query1 = addtional_query
            top_k_docs_new = []

            for k_fact in top_k_facts_new:
                words = []
                k_factt = tuple(k_fact)
                fact_key = compute_mdhash_id(content=str(k_factt), prefix=("fact-"))
                passages_ids = self.fact_to_chunk_ids[fact_key]
                paragraphs = self.chunk_embedding_store.get_rows(passages_ids)
                passss = [paragraphs[rr]['content'] for  rr in passages_ids]
                for word in k_fact:
                    word1 = word.split()
                    words.append(word1)
                for inde,paragraph in enumerate(passss):
                    parts = [part.strip() for part in paragraph.split('\n')]
                    tittl = parts[0]
                    paragraph_1 = ' '.join(parts[1:])
                    sentences = [s.strip() + '.' for s in paragraph_1.lower().split('.') if s.strip()]
                    zzw = 0
                    for sentence in sentences:  
                        scen = tittl.lower()+sentence
                        flag = 0
                        for zz in words:
                            cnt = 0
                            total_cnt =  len(zz)
                            for zy in zz:
                                if zy in scen:
                                    cnt+=1
                            if cnt==total_cnt:
                                flag+=1
                        if flag >=2:
                            if tittl.lower()+'\n'+sentence not in top_k_docs_new:
                                top_k_docs_new.append(tittl.lower()+'\n'+sentence)
                            zzw = 1
                    if zzw != 1:
                        if str(k_factt) not in top_k_docs_new:
                            top_k_docs_new.append(str(k_factt))
                            
            newlog["sentences"] = top_k_docs_new
            newlog["cycle"] = old_message
            logg.append(newlog)
            retrieval_results.append(QuerySolution(question=query, docs=top_k_docs_new,facts=top_k_facts_new))
        retrieve_end_time = time.time()  # Record end time
        filename = f"data_{dataset}_qwen_7b_full_lora_qwen2.5_________100_ab_{self.global_config.ab}_{self.global_config.it}_50.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(logg, f, indent=4, ensure_ascii=False)
        # exit(0)
        self.all_retrieval_time += retrieve_end_time - retrieve_start_time
        return retrieval_results

    def generate_data_ab_fact(self,
                 queries: List[str],
                 num_to_retrieve: int = None,
                 gold_docs: List[List[str]] = None,
               result: Dict[int, List[str]] = None,
               result1: Dict[int, List[str]] = None,
               dataset:str = None) -> List[QuerySolution] | Tuple[List[QuerySolution], Dict]:
         # Record start time

        if gold_docs is not None:
            retrieval_recall_evaluator = RetrievalRecall(global_config=self.global_config)

        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()
        self.get_query_embeddings(queries)
        retrieval_results = []
        logg = []
        rere = 0
        retrieve_start_time = time.time() 
        for q_idx, query in tqdm(enumerate(queries), desc="Retrieving", total=len(queries)):
            query1 = query
            top_k_facts_new = []

            newlog = {}
            newlog["question"] = query1
            paragraphs = result[q_idx]
            tittles = result1[q_idx]
            cnttt = 0
            one_input_template_start = """[[ ## query ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_input_template = """[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_output_template = """[[ ## thought ## ]]\n{thought}\n\n[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## question ## ]]\n{question}"""
            old_message = []
            while query1 != '<no question>' and cnttt < 4:
                cnttt+=1
                query_fact_scores = self.get_fact_scores(query1)
                sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(query1)
                top_k_docs = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:10]]

                top_k_fact_indices, top_k_facts, rerank_log, addtional_query,input_token_count,output_token_count= self.rerank_facts_gene_data(query, query_fact_scores,top_k_docs,tittles,old_message,top_k_facts_new)#三元组在数据库中的位置，三元组
                if cnttt == 1:
                    old_message.append({"role": "user", "content": one_input_template_start.format(question=query1, fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                else:
                    old_message.append({"role": "user", "content": one_input_template.format(fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                newlog.setdefault("new_questions", []).append(addtional_query)
                newlog.setdefault("rerank_log", []).append(rerank_log)

                self.retrieve_input_token_count+=input_token_count
                self.retrieve_output_token_count+=output_token_count

                for j in top_k_facts:
                    if j not in top_k_facts_new:
                        top_k_facts_new.append(j)
                query1 = addtional_query
            newlog["cycle"] = old_message
            logg.append(newlog)

            retrieval_results.append(QuerySolution(question=query,facts=top_k_facts_new))
        retrieve_end_time = time.time()  # Record end time
        filename = f"data_{dataset}_qwen_7b_full_lora_qwen2.5_________100_ab_{self.global_config.ab}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(logg, f, indent=4, ensure_ascii=False)
        self.all_retrieval_time += retrieve_end_time - retrieve_start_time
        return retrieval_results

    def generate_data_ab_passage(self,
                 queries: List[str],
                 num_to_retrieve: int = None,
                 gold_docs: List[List[str]] = None,
               result: Dict[int, List[str]] = None,
               result1: Dict[int, List[str]] = None,
               dataset:str = None) -> List[QuerySolution] | Tuple[List[QuerySolution], Dict]:
         # Record start time

        if num_to_retrieve is None:
            num_to_retrieve = self.global_config.retrieval_top_k

        if gold_docs is not None:
            retrieval_recall_evaluator = RetrievalRecall(global_config=self.global_config)

        if not self.ready_to_retrieve:
            self.prepare_retrieval_objects()
        self.get_query_embeddings(queries)
        retrieval_results = []
        logg = []
        rere = 0
        retrieve_start_time = time.time() 
        for q_idx, query in tqdm(enumerate(queries), desc="Retrieving", total=len(queries)):
            query1 = query
            top_k_facts_new = []

            newlog = {}
            newlog["question"] = query1
            paragraphs = result[q_idx]
            tittles = result1[q_idx]
            cnttt = 0
            one_input_template_start = """[[ ## query ## ]]\n{question}\n\n[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_input_template = """[[ ## fact_before_filter ## ]]\n{fact_before_filter}"""
            one_output_template = """[[ ## thought ## ]]\n{thought}\n\n[[ ## fact_after_filter ## ]]\n{fact_after_filter}\n\n[[ ## question ## ]]\n{question}"""
            old_message = []
            while query1 != '<no question>' and cnttt < 4:
                cnttt+=1
                query_fact_scores = self.get_fact_scores(query1)
                sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(query1)
                top_k_docs = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:10]]

                top_k_fact_indices, top_k_facts, rerank_log, addtional_query,input_token_count,output_token_count= self.rerank_facts_gene_data(query, query_fact_scores,top_k_docs,tittles,old_message,top_k_facts_new)#三元组在数据库中的位置，三元组
                if cnttt == 1:
                    old_message.append({"role": "user", "content": one_input_template_start.format(question=query1, fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                else:
                    old_message.append({"role": "user", "content": one_input_template.format(fact_before_filter=rerank_log["facts_before_filter"])})
                    old_message.append({"role": "assistant", "content": one_output_template.format(thought=rerank_log["thought"],fact_after_filter=rerank_log["facts_after_filter"],question=addtional_query)})
                newlog.setdefault("new_questions", []).append(addtional_query)
                newlog.setdefault("rerank_log", []).append(rerank_log)

                self.retrieve_input_token_count+=input_token_count
                self.retrieve_output_token_count+=output_token_count

                for j in top_k_facts:
                    if j not in top_k_facts_new:
                        top_k_facts_new.append(j)
                query1 = addtional_query
            newlog["cycle"] = old_message
            logg.append(newlog)

            retrieval_results.append(QuerySolution(question=query,facts=top_k_facts_new))
        retrieve_end_time = time.time()  # Record end time
        filename = f"data_{dataset}_qwen_7b_full_lora_qwen2.5_________100_ab_{self.global_config.ab}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(logg, f, indent=4, ensure_ascii=False)
        self.all_retrieval_time += retrieve_end_time - retrieve_start_time
        return retrieval_results
        
    def rag_data_generate(self,
               queries: List[str|QuerySolution],
               gold_docs: List[List[str]] = None,
               gold_answers: List[List[str]] = None,
               result: Dict[int, List[str]] = None,
               result1: Dict[int, List[str]] = None,
               dataset:str = None,
               jj:int = 0) -> Tuple[List[QuerySolution], List[str], List[Dict]] | Tuple[List[QuerySolution], List[str], List[Dict], Dict, Dict]:
        """
        Performs retrieval-augmented generation enhanced QA using the CIRAG .

        This method can handle both string-based queries and pre-processed QuerySolution objects. Depending
        on its inputs, it returns answers only or additionally evaluate retrieval and answer quality using
        recall @ k, exact match and F1 score metrics.

        Parameters:
            queries (List[Union[str, QuerySolution]]): A list of queries, which can be either strings or
                QuerySolution instances. If they are strings, retrieval will be performed.
            gold_docs (Optional[List[List[str]]]): A list of lists containing gold-standard documents for
                each query. This is used if document-level evaluation is to be performed. Default is None.
            gold_answers (Optional[List[List[str]]]): A list of lists containing gold-standard answers for
                each query. Required if evaluation of question answering (QA) answers is enabled. Default
                is None.

        Returns:
            Union[
                Tuple[List[QuerySolution], List[str], List[Dict]],
                Tuple[List[QuerySolution], List[str], List[Dict], Dict, Dict]
            ]: A tuple that always includes:
                - List of QuerySolution objects containing answers and metadata for each query.
                - List of response messages for the provided queries.
                - List of metadata dictionaries for each query.
                If evaluation is enabled, the tuple also includes:
                - A dictionary with overall results from the retrieval phase (if applicable).
                - A dictionary with overall QA evaluation metrics (exact match and F1 scores).

        """
        if gold_answers is not None:
            qa_em_evaluator = QAExactMatch(global_config=self.global_config)
            qa_f1_evaluator = QAF1Score(global_config=self.global_config)

        # Retrieving
        overall_retrieval_result = None
        zz = 0
        qq = 0
        if not isinstance(queries[0], QuerySolution):
            if self.global_config.ab == 'passage':
                queries = self.generate_data_ab_passage(queries=queries,result=result,result1=result1,dataset = dataset)
            elif self.global_config.ab == 'fact':
                queries = self.generate_data_ab_fact(queries=queries,result=result,result1=result1,dataset = dataset)
            elif self.global_config.ab == 'retri':
                queries = self.generate_data_retri(queries=queries,result=result,result1=result1,dataset = dataset)
            else:
                queries = self.generate_data(queries=queries,result=result,result1=result1,dataset = dataset)

        # Performing QA
        qa_start_time = time.time() 
        if self.global_config.ab == 'sentence':
            queries_solutions, all_response_message, all_metadata = self.qa_ab_sentence(queries)
        elif self.global_config.ab == 'passage':
            queries_solutions, all_response_message, all_metadata = self.qa_ab_passage(queries)
        elif self.global_config.ab == 'fact':
            queries_solutions, all_response_message, all_metadata = self.qa_ab_fact(queries)
        elif self.global_config.ab == 'fact-sentence':
            queries_solutions, all_response_message, all_metadata,zz = self.qa_ab_fact_sentence(queries)
        elif self.global_config.ab == 'fact-passage':
            queries_solutions, all_response_message, all_metadata,zz = self.qa_ab_fact_passage(queries)
        elif self.global_config.ab == 'fact-sentence-passage':
            queries_solutions, all_response_message, all_metadata,zz,qq = self.qa_ab_fact_sentence_paasage(queries)
        else:
            # queries_solutions, all_response_message, all_metadata,zz = self.qa_ab_fact_sentence(queries)
            queries_solutions, all_response_message, all_metadata,zz,qq = self.qa_ab_fact_sentence_paasage(queries)
            # queries_solutions, all_response_message, all_metadata,zz = self.qa_copy_new1(queries)
        # queries_solutions, all_response_message, all_metadata = self.qa_copy(queries)
        qa_end_time = time.time() 

        all_qa_time = qa_end_time - qa_end_time
        # Evaluating QA
        if gold_answers is not None:
            overall_qa_em_result, example_qa_em_results = qa_em_evaluator.calculate_metric_scores(
                gold_answers=gold_answers, predicted_answers=[qa_result.answer for qa_result in queries_solutions],
                aggregation_fn=np.max)
            overall_qa_f1_result, example_qa_f1_results = qa_f1_evaluator.calculate_metric_scores(
                gold_answers=gold_answers, predicted_answers=[qa_result.answer for qa_result in queries_solutions],
                aggregation_fn=np.max)

            # round off to 4 decimal places for QA results
            overall_qa_em_result.update(overall_qa_f1_result)
            overall_qa_results = overall_qa_em_result
            overall_qa_results = {k: round(float(v), 4) for k, v in overall_qa_results.items()}
            logger.info(f"Total Retrieval Time {self.all_retrieval_time:.2f}s")
            logger.info(f"Total RetQAieval Time {all_qa_time:.2f}s")
            logger.info(f"Evaluation results for QA: {overall_qa_results}")
            logger.info(f"Total retrieve_input_token {self.retrieve_input_token_count:.2f}")
            logger.info(f"Total retrieve_output_token {self.retrieve_output_token_count:.2f}")
            logger.info(f"Total qa_input_token {self.qa_input_token_count:.2f}")
            logger.info(f"Total qa_output_token {self.qa_output_token_count:.2f}")
            logger.info(f"bili: {zz}")
            logger.info(f"bili: {qq}")
            logger.info(f"{dataset}")
            logger.info(f"{self.global_config.ab}")
            logger.info(f"{self.global_config.it}")
            # Save retrieval and QA results
            for idx, q in enumerate(queries_solutions):
                q.gold_answers = list(gold_answers[idx])
                if gold_docs is not None:
                    q.gold_docs = gold_docs[idx]

            log_file = "qa_eval_results.txt"

            # timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lines = [
                f"==== QA Evaluation @ ====",
                f"Evaluation results for QA: {overall_qa_results}",
                f"Total Retrieval Time {self.all_retrieval_time:.2f}s",
                f"Total retrieve_input_token {self.retrieve_input_token_count:.2f}",
                f"Total retrieve_output_token {self.retrieve_output_token_count:.2f}",
                f"Total qa_input_token {self.qa_input_token_count:.2f}",
                f"Total qa_output_token {self.qa_output_token_count:.2f}",
                f"bili: {zz}",
                f"bili: {qq}",
                f"dataset: {dataset}",
                f"ab: {self.global_config.ab}",
                f"cnt: {jj}",
                f"it: {self.global_config.it}",
                "",  # 空行分隔不同实验
            ]

            # 以“追加模式”写入文件
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            # Save retrieval and QA results
            for idx, q in enumerate(queries_solutions):
                q.gold_answers = list(gold_answers[idx])
                if gold_docs is not None:
                    q.gold_docs = gold_docs[idx]

            dict_list = [qs.to_dict() for qs in queries_solutions]

            # 存储到文件
            filename = f"query_solutions_{dataset}_qwen_7b_full_lora_qwen2.5___________100_ab_{self.global_config.ab}_{jj}_{self.global_config.it}_50.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(dict_list, f, ensure_ascii=False, indent=2)

            return queries_solutions, all_response_message, all_metadata, overall_retrieval_result, overall_qa_results
        else:
            return queries_solutions, all_response_message, all_metadata

    def zzzqa_copy(self, question: str,facts) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA


        sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(question)
        top_k_docs1 = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:5]]
        docs_facts = []
        docs = []
        top_k_docs = []
        for k_factt in facts:
            fact_key = compute_mdhash_id(content=str(k_factt), prefix="fact-")
            passages_ids = self.fact_to_chunk_ids[fact_key]
            paragraphs = self.chunk_embedding_store.get_rows(passages_ids)
            docs.extend(paragraphs[rr]['content'] for rr in passages_ids)
        docs_facts = list(dict.fromkeys(docs))
        needed = 5 - len(docs_facts)
        if needed > 0:
            # 取 top_k_docs1 中未出现的内容
            extra = [d for d in top_k_docs1 if d not in docs_facts]
            # 补齐直到 5 个
            top_k_docs = docs_facts + extra[:needed]
        else:
            top_k_docs = docs_facts[:5]


        # retrieved_passages = query_solution.docs[:self.global_config.qa_top_k]

        prompt_user = ''
        for passage in top_k_docs:
            prompt_user += f'Wikipedia Title: {passage}\n\n'
        prompt_user += 'Question: ' + question + '\nThought: '

        if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_copy_{self.global_config.dataset}_copy'):
            # find the corresponding prompt for this dataset
            prompt_dataset_name = self.global_config.dataset
        else:
            # the dataset does not have a customized prompt template yet
            logger.debug(
                f"rag_qa_copy_{self.global_config.dataset}_copy does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
            prompt_dataset_name = 'musique'
        qa_messages = self.prompt_template_manager.render(name=f'rag_qa_copy_{prompt_dataset_name}_copy', prompt_user=prompt_user)

        qa_results = self.llm_model.infer(qa_messages) 
        response_message, metadata ,cache_hit= qa_results

        try:
            pred_ans = response_message.split('Answer:')[1].strip()
        except Exception as e:
            logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
            pred_ans = response_message

        return pred_ans,top_k_docs

    def zzzqa_fact_sentence1_copy(self, question: str,sentences) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA


        prompt_user = ''
        for passage in sentences:
            prompt_user += f'sentence: {passage}\n\n'
        prompt_user += 'Question: ' + question + '\nThought: '

        if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_reanswer_{self.global_config.dataset}_copy'):
            # find the corresponding prompt for this dataset
            prompt_dataset_name = self.global_config.dataset
        else:
            # the dataset does not have a customized prompt template yet
            logger.debug(
                f"rag_qa_reanswer_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
            prompt_dataset_name = 'musique'
        qa_messages = self.prompt_template_manager.render(name=f'rag_qa_reanswer_{prompt_dataset_name}_copy', prompt_user=prompt_user)

        qa_results = self.llm_model.infer(qa_messages) 
        response_message, metadata ,cache_hit= qa_results

        # try:
        #     pred_ans = response_message.split('Answer:')[1].strip()
        # except Exception as e:
        #     logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
        pred_ans = response_message


        return pred_ans

    def zzzqa_fact_sentence1(self, question: str,sentences) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA


        prompt_user = ''
        for passage in sentences:
            prompt_user += f'sentence: {passage}\n\n'
        prompt_user += 'Question: ' + question + '\nThought: '

        if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_reanswer_{self.global_config.dataset}_copy'):
            # find the corresponding prompt for this dataset
            prompt_dataset_name = self.global_config.dataset
        else:
            # the dataset does not have a customized prompt template yet
            logger.debug(
                f"rag_qa_reanswer_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
            prompt_dataset_name = 'musique'
        qa_messages = self.prompt_template_manager.render(name=f'rag_qa_reanswer_{prompt_dataset_name}_copy', prompt_user=prompt_user)

        qa_results = self.llm_model.infer(qa_messages) 
        response_message, metadata ,cache_hit= qa_results

        try:
            pred_ans = response_message.split('Answer:')[1].strip()
        except Exception as e:
            logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
            pred_ans = response_message


        return pred_ans

    def zzzqa_fact_sentence(self, question: str,sentences) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA


        prompt_user = ''
        for passage in sentences:
            prompt_user += f'sentence: {passage}\n\n'
        prompt_user += 'Question: ' + question + '\nThought: '

        if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_reanswer_{self.global_config.dataset}'):
            # find the corresponding prompt for this dataset
            prompt_dataset_name = self.global_config.dataset
        else:
            # the dataset does not have a customized prompt template yet
            logger.debug(
                f"rag_qa_reanswer_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
            prompt_dataset_name = 'musique'
        qa_messages = self.prompt_template_manager.render(name=f'rag_qa_reanswer_{prompt_dataset_name}', prompt_user=prompt_user)

        qa_results = self.llm_model.infer(qa_messages) 
        response_message, metadata ,cache_hit= qa_results

        try:
            pred_ans = response_message.split('Answer:')[1].strip()
        except Exception as e:
            logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
            pred_ans = response_message

        return pred_ans
    
    
    def zzzqa(self, question: str) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA


        sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(question)
        top_k_docs = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:5]]

        # retrieved_passages = query_solution.docs[:self.global_config.qa_top_k]

        prompt_user = ''
        for passage in top_k_docs:
            prompt_user += f'Wikipedia Title: {passage}\n\n'
        prompt_user += 'Question: ' + question + '\nThought: '

        if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_copy_{self.global_config.dataset}_copy'):
            # find the corresponding prompt for this dataset
            prompt_dataset_name = self.global_config.dataset
        else:
            # the dataset does not have a customized prompt template yet
            logger.debug(
                f"rag_qa_copy_{self.global_config.dataset}_copy does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
            prompt_dataset_name = 'musique'
        qa_messages = self.prompt_template_manager.render(name=f'rag_qa_copy_{prompt_dataset_name}_copy', prompt_user=prompt_user)

        qa_results = self.llm_model.infer(qa_messages) 
        response_message, metadata ,cache_hit= qa_results

        try:
            pred_ans = response_message.split('Answer:')[1].strip()
        except Exception as e:
            logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
            pred_ans = response_message

        return pred_ans,top_k_docs
    
    def qa_copy_new(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA
        all_qa_messages = []
        zz = 0

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            retrieved_facts = query_solution.docs[:self.global_config.qa_top_k]
            prompt_user = ''
            for passage in retrieved_facts:
                
                # prompt_user += f'Wikipedia Title: {passage}\n\n'
                prompt_user += f'sentence: {passage}\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_copy_new_{self.global_config.dataset}'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_copy_new_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        # all_qa_results = []
        # for qa_messages in tqdm(all_qa_messages, desc="QA Reading"):
        #     result = self.llm_model.infer(qa_messages)

        #     all_qa_results.append(result)
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            try:
                pred_ans = response_content.split('Answer:')[1].strip()
            except Exception as e:
                logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
                pred_ans = response_content
            if pred_ans == 'cannot be determined from the provided information':
                pred_ans,tok_fact = self.zzzqa(query_solution.question)
                zz+=1
                print(zz)
                query_solution.docs = tok_fact

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata,zz
    
    def qa_copy_new1(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA
        all_qa_messages = []
        zz = 0

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            retrieved_facts = query_solution.docs
            prompt_user = ''
            for passage in retrieved_facts:
                
                # prompt_user += f'Wikipedia Title: {passage}\n\n'
                prompt_user += f'sentence: {passage}\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_reanswer_{self.global_config.dataset}'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_reanswer_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_reanswer_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        # all_qa_results = []
        # for qa_messages in tqdm(all_qa_messages, desc="QA Reading"):
        #     result = self.llm_model.infer(qa_messages)

        #     all_qa_results.append(result)
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            self.qa_input_token_count += all_metadata[query_solution_idx]["prompt_tokens"]
            self.qa_output_token_count += all_metadata[query_solution_idx]["completion_tokens"]
            question = queries[query_solution_idx].question
            # print(response_content)

            pred_ans = self.reanswer1.arun(1, placeholder={
            "question": question,
            "response": response_content,
            })
            # print(pred_ans)
            # try:
            #     pred_ans = response_content.split('Answer:')[1].strip()
            # except Exception as e:
            #     logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
            #     pred_ans = response_content
            if pred_ans == 'No answer':
                # pred_ans,tok_fact = self.zzzqa(query_solution.question)
                pred_ans,tok_fact = self.zzzqa_copy(query_solution.question,query_solution.facts)
                zz+=1
                # print(zz)
                query_solution.docs = tok_fact
                pred_ans = self.reanswer.arun(1, placeholder={
                "question": question,
                "response": pred_ans,
                })

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata,zz

    def qa_copy(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA
        all_qa_messages = []

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            # retrieved_facts = query_solution.docs[:self.global_config.qa_top_k]
            retrieved_facts = query_solution.docs
            prompt_user = ''
            for passage in retrieved_facts:
                
                # prompt_user += f'Wikipedia Title: {passage}\n\n'
                prompt_user += f'sentence: {passage}\n\n'
            # prompt_user += 'Question: ' + query_solution.question + '\nThought: '
            prompt_user += 'Question: ' + query_solution.question + '\n'

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_copy_{self.global_config.dataset}'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_copy_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            try:
                pred_ans = response_content.split('Answer:')[1].strip()
            except Exception as e:
                logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
                pred_ans = response_content

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata
    def qa_ab_fact_passage(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA
        all_qa_messages = []
        zz = 0

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            # retrieved_facts = query_solution.docs[:self.global_config.qa_top_k]
            retrieved_facts = query_solution.facts
            tuple_list = [tuple(item) for item in retrieved_facts]
            prompt_user = "triplets: " + ", ".join(str(t) for t in tuple_list) + '\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_ab_fact_{self.global_config.dataset}'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_ab_fact_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_ab_fact_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            self.qa_input_token_count += all_metadata[query_solution_idx]["prompt_tokens"]
            self.qa_output_token_count += all_metadata[query_solution_idx]["completion_tokens"]
            question = queries[query_solution_idx].question
            # print(response_content)
            pred_ans = self.reanswer1.arun(1, placeholder={
            "question": question,
            "response": response_content,
            })

            if pred_ans == 'No answer':
                # pred_ans,tok_fact = self.zzzqa(query_solution.question)
                pred_ans,tok_fact = self.zzzqa_copy(query_solution.question,query_solution.facts)
                # pred_ans = self.zzzqa_fact_sentence(query_solution.question,query_solution.docs)
                zz+=1
                # print(zz)
                query_solution.docs = tok_fact
                pred_ans = self.reanswer.arun(1, placeholder={
                "question": question,
                "response": pred_ans,
                })

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata,zz


    def qa_ab_fact_sentence_paasage(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA
        all_qa_messages = []
        zz = 0
        qq = 0

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            # retrieved_facts = query_solution.docs[:self.global_config.qa_top_k]
            retrieved_facts = query_solution.facts
            tuple_list = [tuple(item) for item in retrieved_facts]
            prompt_user = "triplets: " + ", ".join(str(t) for t in tuple_list) + '\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_ab_fact_{self.global_config.dataset}_copy'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_ab_fact_{self.global_config.dataset}_copy does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_ab_fact_{prompt_dataset_name}_copy', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            self.qa_input_token_count += all_metadata[query_solution_idx]["prompt_tokens"]
            self.qa_output_token_count += all_metadata[query_solution_idx]["completion_tokens"]
            question = queries[query_solution_idx].question
            # print(response_content)
            if 'No answer' in response_content:
                pred_ans = self.zzzqa_fact_sentence1(query_solution.question,query_solution.docs)
                if 'No answer' in pred_ans:
                    query_solution.g_type ="passage"
                    qq+=1
                    pred_ans = self.zzzqa_copy(query_solution.question,query_solution.facts)
                else:
                    query_solution.g_type ="sentence"
                    zz+=1
            else:
                query_solution.g_type ="triple"
                pred_ans = response_content
            pred_ans = self.reanswer.arun(1, placeholder={
                            "question": question,
                            "response": pred_ans,
                            })

            # if pred_ans == 'No answer':
            #     # pred_ans,tok_fact = self.zzzqa(query_solution.question)
            #     pred_ans = self.zzzqa_fact_sentence(query_solution.question,query_solution.docs)
            #     zz+=1
            #     # print(zz)
            #     pred_ans = self.reanswer1.arun(1, placeholder={
            #     "question": question,
            #     "response": pred_ans,
            #     })
            #     if pred_ans == 'No answer':
            #         pred_ans = self.zzzqa_copy(query_solution.question,query_solution.facts)
            #         zz-=1
            #         qq+=1
            #         pred_ans = self.reanswer.arun(1, placeholder={
            #                         "question": question,
            #                         "response": pred_ans,
            #                         })
            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata,zz,qq

    def qa_ab_fact_sentence(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA
        all_qa_messages = []
        zz = 0

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            # retrieved_facts = query_solution.docs[:self.global_config.qa_top_k]
            retrieved_facts = query_solution.facts
            tuple_list = [tuple(item) for item in retrieved_facts]
            prompt_user = "triplets: " + ", ".join(str(t) for t in tuple_list) + '\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_ab_fact_{self.global_config.dataset}'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_ab_fact_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_ab_fact_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            self.qa_input_token_count += all_metadata[query_solution_idx]["prompt_tokens"]
            self.qa_output_token_count += all_metadata[query_solution_idx]["completion_tokens"]
            question = queries[query_solution_idx].question
            # print(response_content)
            pred_ans = self.reanswer1.arun(1, placeholder={
            "question": question,
            "response": response_content,
            })

            if pred_ans == 'No answer':
                # pred_ans,tok_fact = self.zzzqa(query_solution.question)
                pred_ans = self.zzzqa_fact_sentence(query_solution.question,query_solution.docs)
                zz+=1
                # print(zz)
                pred_ans = self.reanswer.arun(1, placeholder={
                "question": question,
                "response": pred_ans,
                })

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata,zz
    def qa_ab_fact(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        #Running inference for QA
        all_qa_messages = []

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            # retrieved_facts = query_solution.docs[:self.global_config.qa_top_k]
            retrieved_facts = query_solution.facts
            tuple_list = [tuple(item) for item in retrieved_facts]
            prompt_user = "triplets: " + ", ".join(str(t) for t in tuple_list) + '\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_ab_fact_{self.global_config.dataset}'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_ab_fact_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_ab_fact_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            self.qa_input_token_count += all_metadata[query_solution_idx]["prompt_tokens"]
            self.qa_output_token_count += all_metadata[query_solution_idx]["completion_tokens"]
            question = queries[query_solution_idx].question
            # print(response_content)
            pred_ans = self.reanswer.arun(1, placeholder={
            "question": question,
            "response": response_content,
            })

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata
    
    def qa_ab_passage(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:

        #Running inference for QA
        all_qa_messages = []

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            question = query_solution.question
            facts = query_solution.facts
            # retrieved_facts = query_solution.docs[:self.global_config.qa_top_k]
            sorted_doc_ids, sorted_doc_scores = self.dense_passage_retrieval(question)
            top_k_docs1 = [self.chunk_embedding_store.get_row(self.passage_node_keys[idx])["content"] for idx in sorted_doc_ids[:5]]
            docs_facts = []
            docs = []
            top_k_docs = []
            for k_factt in facts:
                fact_key = compute_mdhash_id(content=str(k_factt), prefix="fact-")
                passages_ids = self.fact_to_chunk_ids[fact_key]
                paragraphs = self.chunk_embedding_store.get_rows(passages_ids)
                docs.extend(paragraphs[rr]['content'] for rr in passages_ids)
            docs_facts = list(dict.fromkeys(docs))
            needed = 5 - len(docs_facts)
            if needed > 0:
                # 取 top_k_docs1 中未出现的内容
                extra = [d for d in top_k_docs1 if d not in docs_facts]
                # 补齐直到 5 个
                top_k_docs = docs_facts + extra[:needed]
            else:
                top_k_docs = docs_facts[:5]


            prompt_user = ''
            for passage in top_k_docs:
                prompt_user += f'Wikipedia Title: {passage}\n\n'
            prompt_user += 'Question: ' + question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_copy_{self.global_config.dataset}_copy'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_copy_{self.global_config.dataset}_copy does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_copy_{prompt_dataset_name}_copy', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            self.qa_input_token_count += all_metadata[query_solution_idx]["prompt_tokens"]
            self.qa_output_token_count += all_metadata[query_solution_idx]["completion_tokens"]
            question = queries[query_solution_idx].question
            # print(response_content)
            pred_ans = self.reanswer.arun(1, placeholder={
            "question": question,
            "response": response_content,
            })

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata
    
    def qa_ab_sentence(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        #Running inference for QA
        all_qa_messages = []

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            retrieved_facts = query_solution.docs
            prompt_user = ''
            for passage in retrieved_facts:
                prompt_user += f'sentence: {passage}\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_ab_sentence_{self.global_config.dataset}'):
                prompt_dataset_name = self.global_config.dataset
            else:
                logger.debug(
                    f"rag_qa_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_ab_sentence_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]
        
        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        #Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            self.qa_input_token_count += all_metadata[query_solution_idx]["prompt_tokens"]
            self.qa_output_token_count += all_metadata[query_solution_idx]["completion_tokens"]
            question = queries[query_solution_idx].question
            # print(response_content)
            pred_ans = self.reanswer.arun(1, placeholder={
            "question": question,
            "response": response_content,
            })

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata

    def add_fact_edges(self, chunk_ids: List[str], chunk_triples: List[Tuple]):
        """
        Adds fact edges from given triples to the graph.

        The method processes chunks of triples, computes unique identifiers
        for entities and relations, and updates various internal statistics
        to build and maintain the graph structure. Entities are uniquely
        identified and linked based on their relationships.

        Parameters:
            chunk_ids: List[str]
                A list of unique identifiers for the chunks being processed.
            chunk_triples: List[Tuple]
                A list of tuples representing triples to process. Each triple
                consists of a subject, predicate, and object.

        Raises:
            Does not explicitly raise exceptions within the provided function logic.
        """

        if "name" in self.graph.vs:
            current_graph_nodes = set(self.graph.vs["name"])
        else:
            current_graph_nodes = set()

        logger.info(f"Adding OpenIE triples to graph.")

        for chunk_key, triples in tqdm(zip(chunk_ids, chunk_triples)):
            entities_in_chunk = set()

            if chunk_key not in current_graph_nodes:
                for triple in triples:
                    triple = tuple(triple)

                    node_key = compute_mdhash_id(content=triple[0], prefix=("entity-"))
                    node_2_key = compute_mdhash_id(content=triple[2], prefix=("entity-"))

                    self.node_to_node_stats[(node_key, node_2_key)] = self.node_to_node_stats.get(
                        (node_key, node_2_key), 0.0) + 1
                    self.node_to_node_stats[(node_2_key, node_key)] = self.node_to_node_stats.get(
                        (node_2_key, node_key), 0.0) + 1

                    entities_in_chunk.add(node_key)
                    entities_in_chunk.add(node_2_key)

                for node in entities_in_chunk:
                    self.ent_node_to_chunk_ids[node] = self.ent_node_to_chunk_ids.get(node, set()).union(set([chunk_key]))

    def add_fact(self, chunk_ids: List[str], chunk_triples: List[Tuple]):

        logger.info(f"Adding OpenIE triples to graph.")

        for chunk_key, triples in tqdm(zip(chunk_ids, chunk_triples)):
            for triple in triples:
                triple = tuple(triple)
                fact_key = compute_mdhash_id(content=str(triple), prefix=("fact-"))
                self.fact_to_chunk_ids.setdefault(fact_key, set()).add(chunk_key)

    def add_sentence(self, chunk_ids: List[str], chunk_triples: List[Tuple]):

        logger.info(f"Adding OpenIE sentence to graph.")

        for chunk_key, triples in tqdm(zip(chunk_ids, chunk_triples)):
            for triple in triples:
                words = []
                triple = tuple(triple)
                fact_key = compute_mdhash_id(content=str(triple), prefix=("fact-"))
                paragraph = self.chunk_embedding_store.get_row(chunk_key)['content']
                for word in triple:
                    word1 = word.split()
                    words.append(word1)
                parts = [part.strip() for part in paragraph.split('\n')]
                tittl = parts[0]
                paragraph_1 = ' '.join(parts[1:])
                sentences = [s.strip() + '.' for s in paragraph_1.lower().split('.') if s.strip()]
                zzw = 0
                for index,sentence in enumerate(sentences):  
                    scen = tittl.lower()+sentence
                    flag = 0
                    for zz in words:
                        cnt = 0
                        total_cnt =  len(zz)
                        for zy in zz:
                            if zy in scen:
                                cnt+=1
                        if cnt==total_cnt:
                            flag+=1
                    if flag >=2:
                        self.fact_to_sentence_ids.setdefault(fact_key, {}).setdefault(chunk_key, []).append(index)
                        zzw = 1
                if zzw != 1:
                    self.fact_to_sentence_ids.setdefault(fact_key, {}).setdefault(chunk_key, []).append(-1)


    def add_passage_edges(self, chunk_ids: List[str], chunk_triple_entities: List[List[str]]):
        """
        Adds edges connecting passage nodes to phrase nodes in the graph.

        This method is responsible for iterating through a list of chunk identifiers
        and their corresponding triple entities. It calculates and adds new edges
        between the passage nodes (defined by the chunk identifiers) and the phrase
        nodes (defined by the computed unique hash IDs of triple entities). The method
        also updates the node-to-node statistics map and keeps count of newly added
        passage nodes.

        Parameters:
            chunk_ids : List[str]
                A list of identifiers representing passage nodes in the graph.
            chunk_triple_entities : List[List[str]]
                A list of lists where each sublist contains entities (strings) associated
                with the corresponding chunk in the chunk_ids list.

        Returns:
            int
                The number of new passage nodes added to the graph.
        """

        if "name" in self.graph.vs.attribute_names():
            current_graph_nodes = set(self.graph.vs["name"])
        else:
            current_graph_nodes = set()

        num_new_chunks = 0

        logger.info(f"Connecting passage nodes to phrase nodes.")

        for idx, chunk_key in tqdm(enumerate(chunk_ids)):

            if chunk_key not in current_graph_nodes:
                for chunk_ent in chunk_triple_entities[idx]:
                    node_key = compute_mdhash_id(chunk_ent, prefix="entity-")

                    self.node_to_node_stats[(chunk_key, node_key)] = 1.0

                num_new_chunks += 1

        return num_new_chunks

    def add_synonymy_edges(self):
        """
        Adds synonymy edges between similar nodes in the graph to enhance connectivity by identifying and linking synonym entities.

        This method performs key operations to compute and add synonymy edges. It first retrieves embeddings for all nodes, then conducts
        a nearest neighbor (KNN) search to find similar nodes. These similar nodes are identified based on a score threshold, and edges
        are added to represent the synonym relationship.

        Attributes:
            entity_id_to_row: dict (populated within the function). Maps each entity ID to its corresponding row data, where rows
                              contain `content` of entities used for comparison.
            entity_embedding_store: Manages retrieval of texts and embeddings for all rows related to entities.
            global_config: Configuration object that defines parameters such as `synonymy_edge_topk`, `synonymy_edge_sim_threshold`,
                           `synonymy_edge_query_batch_size`, and `synonymy_edge_key_batch_size`.
            node_to_node_stats: dict. Stores scores for edges between nodes representing their relationship.

        """
        logger.info(f"Expanding graph with synonymy edges")

        self.entity_id_to_row = self.entity_embedding_store.get_all_id_to_rows()
        entity_node_keys = list(self.entity_id_to_row.keys())

        logger.info(f"Performing KNN retrieval for each phrase nodes ({len(entity_node_keys)}).")

        entity_embs = self.entity_embedding_store.get_embeddings(entity_node_keys)

        # Here we build synonymy edges only between newly inserted phrase nodes and all phrase nodes in the storage to reduce cost for incremental graph updates
        query_node_key2knn_node_keys = retrieve_knn(query_ids=entity_node_keys,
                                                    key_ids=entity_node_keys,
                                                    query_vecs=entity_embs,
                                                    key_vecs=entity_embs,
                                                    k=self.global_config.synonymy_edge_topk,
                                                    query_batch_size=self.global_config.synonymy_edge_query_batch_size,
                                                    key_batch_size=self.global_config.synonymy_edge_key_batch_size)

        num_synonym_triple = 0
        synonym_candidates = []  # [(node key, [(synonym node key, corresponding score), ...]), ...]

        for node_key in tqdm(query_node_key2knn_node_keys.keys(), total=len(query_node_key2knn_node_keys)):
            synonyms = []

            entity = self.entity_id_to_row[node_key]["content"]

            if len(re.sub('[^A-Za-z0-9]', '', entity)) > 2:
                nns = query_node_key2knn_node_keys[node_key]

                num_nns = 0
                for nn, score in zip(nns[0], nns[1]):
                    if score < self.global_config.synonymy_edge_sim_threshold or num_nns > 100:
                        break

                    nn_phrase = self.entity_id_to_row[nn]["content"]

                    if nn != node_key and nn_phrase != '':
                        sim_edge = (node_key, nn)
                        synonyms.append((nn, score))
                        num_synonym_triple += 1

                        self.node_to_node_stats[sim_edge] = score  # Need to seriously discuss on this
                        num_nns += 1

            synonym_candidates.append((node_key, synonyms))

    def load_existing_openie(self, chunk_keys: List[str]) -> Tuple[List[dict], Set[str]]:
        """
        Loads existing OpenIE results from the specified file if it exists and combines
        them with new content while standardizing indices. If the file does not exist or
        is configured to be re-initialized from scratch with the flag `force_openie_from_scratch`,
        it prepares new entries for processing.

        Args:
            chunk_keys (List[str]): A list of chunk keys that represent identifiers
                                     for the content to be processed.

        Returns:
            Tuple[List[dict], Set[str]]: A tuple where the first element is the existing OpenIE
                                         information (if any) loaded from the file, and the
                                         second element is a set of chunk keys that still need to
                                         be saved or processed.
        """

        # combine openie_results with contents already in file, if file exists
        chunk_keys_to_save = set()

        if not self.global_config.force_openie_from_scratch and os.path.isfile(self.openie_results_path):
            openie_results = json.load(open(self.openie_results_path))
            # print(self.openie_results_path)
            all_openie_info = openie_results.get('docs', [])

            # print(len(all_openie_info))

            #Standardizing indices for OpenIE Files.
            # print(len(all_openie_info))
            renamed_openie_info = []
            for openie_info in all_openie_info:
                # result1 = openie_info['passage'].split('\n', 1)[1]
                # openie_info['idx'] = compute_mdhash_id(result1, 'chunk-')
                # openie_info['idx'] = compute_mdhash_id(openie_info['passage'], 'chunk-')
                openie_info['idx'] = compute_mdhash_id(openie_info['passage'], 'chunk-')
                renamed_openie_info.append(openie_info)

            all_openie_info = renamed_openie_info

            existing_openie_keys = set([info['idx'] for info in all_openie_info])
            # print(len(chunk_keys_to_save))
            for chunk_key in chunk_keys:
                if chunk_key not in existing_openie_keys:
                    chunk_keys_to_save.add(chunk_key)
            # print(len(chunk_keys_to_save))
        else:
            all_openie_info = []
            chunk_keys_to_save = chunk_keys
            

        return all_openie_info, chunk_keys_to_save

    def merge_openie_results(self,
                             all_openie_info: List[dict],
                             chunks_to_save: Dict[str, dict],
                             ner_results_dict: Dict[str, NerRawOutput],
                             triple_results_dict: Dict[str, TripleRawOutput]) -> List[dict]:
        """
        Merges OpenIE extraction results with corresponding passage and metadata.

        This function integrates the OpenIE extraction results, including named-entity
        recognition (NER) entities and triples, with their respective text passages
        using the provided chunk keys. The resulting merged data is appended to
        the `all_openie_info` list containing dictionaries with combined and organized
        data for further processing or storage.

        Parameters:
            all_openie_info (List[dict]): A list to hold dictionaries of merged OpenIE
                results and metadata for all chunks.
            chunks_to_save (Dict[str, dict]): A dict of chunk identifiers (keys) to process
                and merge OpenIE results to dictionaries with `hash_id` and `content` keys.
            ner_results_dict (Dict[str, NerRawOutput]): A dictionary mapping chunk keys
                to their corresponding NER extraction results.
            triple_results_dict (Dict[str, TripleRawOutput]): A dictionary mapping chunk
                keys to their corresponding OpenIE triple extraction results.

        Returns:
            List[dict]: The `all_openie_info` list containing dictionaries with merged
            OpenIE results, metadata, and the passage content for each chunk.

        """

        for chunk_key, row in chunks_to_save.items():
            passage = row['content']
            chunk_openie_info = {'idx': chunk_key, 'passage': passage,
                                 'extracted_entities': ner_results_dict[chunk_key].unique_entities,
                                 'extracted_triples': triple_results_dict[chunk_key].triples}
            # chunk_openie_info = {'idx': chunk_key, 'passage': passage,
            #                      'extracted_entities': ner_results_dict[chunk_key].unique_entities,
            #                      'extracted_triples': triple_results_dict[chunk_key].triples,
            #                      'passage_woti':''}
            all_openie_info.append(chunk_openie_info)

        return all_openie_info

    def save_openie_results(self, all_openie_info: List[dict]):
        """
        Computes statistics on extracted entities from OpenIE results and saves the aggregated data in a
        JSON file. The function calculates the average character and word lengths of the extracted entities
        and writes them along with the provided OpenIE information to a file.

        Parameters:
            all_openie_info : List[dict]
                List of dictionaries, where each dictionary represents information from OpenIE, including
                extracted entities.
        """

        sum_phrase_chars = sum([len(e) for chunk in all_openie_info for e in chunk['extracted_entities']])
        sum_phrase_words = sum([len(e.split()) for chunk in all_openie_info for e in chunk['extracted_entities']])
        num_phrases = sum([len(chunk['extracted_entities']) for chunk in all_openie_info])

        if len(all_openie_info) > 0:
            openie_dict = {'docs': all_openie_info, 'avg_ent_chars': round(sum_phrase_chars / num_phrases, 4),
                           'avg_ent_words': round(sum_phrase_words / num_phrases, 4)}
            with open(self.openie_results_path, 'w') as f:
                json.dump(openie_dict, f)
            logger.info(f"OpenIE results saved to {self.openie_results_path}")

    def augment_graph(self):
        """
        Provides utility functions to augment a graph by adding new nodes and edges.
        It ensures that the graph structure is extended to include additional components,
        and logs the completion status along with printing the updated graph information.
        """

        self.add_new_nodes()
        self.add_new_edges()

        logger.info(f"Graph construction completed!")
        print(self.get_graph_info())

    def add_new_nodes(self):
        """
        Adds new nodes to the graph from entity and passage embedding stores based on their attributes.

        This method identifies and adds new nodes to the graph by comparing existing nodes
        in the graph and nodes retrieved from the entity embedding store and the passage
        embedding store. The method checks attributes and ensures no duplicates are added.
        New nodes are prepared and added in bulk to optimize graph updates.
        """

        existing_nodes = {v["name"]: v for v in self.graph.vs if "name" in v.attributes()}

        entity_to_row = self.entity_embedding_store.get_all_id_to_rows()
        passage_to_row = self.chunk_embedding_store.get_all_id_to_rows()

        node_to_rows = entity_to_row
        node_to_rows.update(passage_to_row)

        new_nodes = {}
        for node_id, node in node_to_rows.items():
            node['name'] = node_id
            if node_id not in existing_nodes:
                for k, v in node.items():
                    if k not in new_nodes:
                        new_nodes[k] = []
                    new_nodes[k].append(v)

        if len(new_nodes) > 0:
            self.graph.add_vertices(n=len(next(iter(new_nodes.values()))), attributes=new_nodes)

    def add_new_edges(self):
        """
        Processes edges from `node_to_node_stats` to add them into a graph object while
        managing adjacency lists, validating edges, and logging invalid edge cases.
        """

        graph_adj_list = defaultdict(dict)
        graph_inverse_adj_list = defaultdict(dict)
        edge_source_node_keys = []
        edge_target_node_keys = []
        edge_metadata = []
        for edge, weight in self.node_to_node_stats.items():
            if edge[0] == edge[1]: continue
            graph_adj_list[edge[0]][edge[1]] = weight
            graph_inverse_adj_list[edge[1]][edge[0]] = weight

            edge_source_node_keys.append(edge[0])
            edge_target_node_keys.append(edge[1])
            edge_metadata.append({
                "weight": weight
            })

        valid_edges, valid_weights = [], {"weight": []}
        current_node_ids = set(self.graph.vs["name"])
        for source_node_id, target_node_id, edge_d in zip(edge_source_node_keys, edge_target_node_keys, edge_metadata):
            if source_node_id in current_node_ids and target_node_id in current_node_ids:
                valid_edges.append((source_node_id, target_node_id))
                weight = edge_d.get("weight", 1.0)
                valid_weights["weight"].append(weight)
            else:
                logger.warning(f"Edge {source_node_id} -> {target_node_id} is not valid.")
        self.graph.add_edges(
            valid_edges,
            attributes=valid_weights
        )

    def save_igraph(self):
        logger.info(
            f"Writing graph with {len(self.graph.vs())} nodes, {len(self.graph.es())} edges"
        )
        self.graph.write_pickle(self._graph_pickle_filename)
        logger.info(f"Saving graph completed!")

    def get_graph_info(self) -> Dict:
        """
        Obtains detailed information about the graph such as the number of nodes,
        triples, and their classifications.

        This method calculates various statistics about the graph based on the
        stores and node-to-node relationships, including counts of phrase and
        passage nodes, total nodes, extracted triples, triples involving passage
        nodes, synonymy triples, and total triples.

        Returns:
            Dict
                A dictionary containing the following keys and their respective values:
                - num_phrase_nodes: The number of unique phrase nodes.
                - num_passage_nodes: The number of unique passage nodes.
                - num_total_nodes: The total number of nodes (sum of phrase and passage nodes).
                - num_extracted_triples: The number of unique extracted triples.
                - num_triples_with_passage_node: The number of triples involving at least one
                  passage node.
                - num_synonymy_triples: The number of synonymy triples (distinct from extracted
                  triples and those with passage nodes).
                - num_total_triples: The total number of triples.
        """
        graph_info = {}

        # get # of phrase nodes
        phrase_nodes_keys = self.entity_embedding_store.get_all_ids()
        graph_info["num_phrase_nodes"] = len(set(phrase_nodes_keys))

        # get # of passage nodes
        passage_nodes_keys = self.chunk_embedding_store.get_all_ids()
        graph_info["num_passage_nodes"] = len(set(passage_nodes_keys))

        # get # of total nodes
        graph_info["num_total_nodes"] = graph_info["num_phrase_nodes"] + graph_info["num_passage_nodes"]

        # get # of extracted triples
        graph_info["num_extracted_triples"] = len(self.fact_embedding_store.get_all_ids())

        num_triples_with_passage_node = 0
        passage_nodes_set = set(passage_nodes_keys)
        num_triples_with_passage_node = sum(
            1 for node_pair in self.node_to_node_stats
            if node_pair[0] in passage_nodes_set or node_pair[1] in passage_nodes_set
        )
        graph_info['num_triples_with_passage_node'] = num_triples_with_passage_node

        graph_info['num_synonymy_triples'] = len(self.node_to_node_stats) - graph_info[
            "num_extracted_triples"] - num_triples_with_passage_node

        # get # of total triples
        graph_info["num_total_triples"] = len(self.node_to_node_stats)

        return graph_info

    def prepare_retrieval_objects(self):
        """
        Prepares various in-memory objects and attributes necessary for fast retrieval processes, such as embedding data and graph relationships, ensuring consistency
        and alignment with the underlying graph structure.
        """

        logger.info("Preparing for fast retrieval.")

        logger.info("Loading keys.")
        self.query_to_embedding: Dict = {'triple': {}, 'passage': {}}

        self.entity_node_keys: List = list(self.entity_embedding_store.get_all_ids()) # a list of phrase node keys
        self.passage_node_keys: List = list(self.chunk_embedding_store.get_all_ids()) # a list of passage node keys
        self.fact_node_keys: List = list(self.fact_embedding_store.get_all_ids())

        assert len(self.entity_node_keys) + len(self.passage_node_keys) == self.graph.vcount()

        igraph_name_to_idx = {node["name"]: idx for idx, node in enumerate(self.graph.vs)} # from node key to the index in the backbone graph
        self.node_name_to_vertex_idx = igraph_name_to_idx
        self.entity_node_idxs = [igraph_name_to_idx[node_key] for node_key in self.entity_node_keys] # a list of backbone graph node index
        self.passage_node_idxs = [igraph_name_to_idx[node_key] for node_key in self.passage_node_keys] # a list of backbone passage node index

        logger.info("Loading embeddings.")
        # print("1")
        # print(self.entity_embedding_store.get_embedding('entity-ea6e3c1ec23019fbb2cd6ce86dd8338c'))
        # exit(0)

        self.entity_embeddings = np.array(self.entity_embedding_store.get_embeddings(self.entity_node_keys))
        # print("2")
        self.passage_embeddings = np.array(self.chunk_embedding_store.get_embeddings(self.passage_node_keys))
        # print("3")

        self.fact_embeddings = np.array(self.fact_embedding_store.get_embeddings(self.fact_node_keys))
        # print("4")
        all_openie_info, chunk_keys_to_process = self.load_existing_openie([])
        # print("5")

        self.proc_triples_to_docs = {}

        for doc in all_openie_info:
            triples = flatten_facts([doc['extracted_triples']])
            for triple in triples:
                if len(triple) == 3:
                    proc_triple = tuple(text_processing(list(triple)))
                    self.proc_triples_to_docs[str(proc_triple)] = self.proc_triples_to_docs.get(str(proc_triple), set()).union(set([doc['idx']]))
        # print("5")

        if self.ent_node_to_chunk_ids is None:
            ner_results_dict, triple_results_dict = reformat_openie_results(all_openie_info)

            assert len(self.passage_node_keys) == len(ner_results_dict) == len(triple_results_dict), print((len(self.passage_node_keys), len(ner_results_dict), len(triple_results_dict)))

            # prepare data_store
            chunk_triples = [[text_processing(t) for t in triple_results_dict[chunk_id].triples] for chunk_id in self.passage_node_keys]

            self.node_to_node_stats = {}
            self.ent_node_to_chunk_ids = {}
            self.add_fact_edges(self.passage_node_keys, chunk_triples)

        self.ready_to_retrieve = True

    def get_query_embeddings(self, queries: List[str] | List[QuerySolution]):
        """
        Retrieves embeddings for given queries and updates the internal query-to-embedding mapping. The method determines whether each query
        is already present in the `self.query_to_embedding` dictionary under the keys 'triple' and 'passage'. If a query is not present in
        either, it is encoded into embeddings using the embedding model and stored.

        Args:
            queries List[str] | List[QuerySolution]: A list of query strings or QuerySolution objects. Each query is checked for
            its presence in the query-to-embedding mappings.
        """

        all_query_strings = []
        for query in queries:
            if isinstance(query, QuerySolution) and (
                    query.question not in self.query_to_embedding['triple'] or query.question not in
                    self.query_to_embedding['passage']):
                all_query_strings.append(query.question)
            elif query not in self.query_to_embedding['triple'] or query not in self.query_to_embedding['passage']:
                all_query_strings.append(query)

        if len(all_query_strings) > 0:
            # get all query embeddings
            logger.info(f"Encoding {len(all_query_strings)} queries for query_to_fact.")
            query_embeddings_for_triple = self.embedding_model.batch_encode(all_query_strings,
                                                                            instruction=get_query_instruction('query_to_fact'),
                                                                            norm=True)
            for query, embedding in zip(all_query_strings, query_embeddings_for_triple):
                self.query_to_embedding['triple'][query] = embedding

            logger.info(f"Encoding {len(all_query_strings)} queries for query_to_passage.")
            query_embeddings_for_passage = self.embedding_model.batch_encode(all_query_strings,
                                                                             instruction=get_query_instruction('query_to_passage'),
                                                                             norm=True)
            for query, embedding in zip(all_query_strings, query_embeddings_for_passage):
                self.query_to_embedding['passage'][query] = embedding

    def get_fact_scores(self, query: str) -> np.ndarray:
        """
        Retrieves and computes normalized similarity scores between the given query and pre-stored fact embeddings.

        Parameters:
        query : str
            The input query text for which similarity scores with fact embeddings
            need to be computed.

        Returns:
        numpy.ndarray
            A normalized array of similarity scores between the query and fact
            embeddings. The shape of the array is determined by the number of
            facts.

        Raises:
        KeyError
            If no embedding is found for the provided query in the stored query
            embeddings dictionary.
        """
        query_embedding = self.query_to_embedding['triple'].get(query, None)
        if query_embedding is None:
            query_embedding = self.embedding_model.batch_encode(query,
                                                                instruction=get_query_instruction('query_to_fact'),
                                                                norm=True)

        query_fact_scores = np.dot(self.fact_embeddings, query_embedding.T) # shape: (#facts, )
        query_fact_scores = np.squeeze(query_fact_scores) if query_fact_scores.ndim == 2 else query_fact_scores
        query_fact_scores = min_max_normalize(query_fact_scores)

        return query_fact_scores

    def dense_passage_retrieval(self, query: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Conduct dense passage retrieval to find relevant documents for a query.

        This function processes a given query using a pre-trained embedding model
        to generate query embeddings. The similarity scores between the query
        embedding and passage embeddings are computed using dot product, followed
        by score normalization. Finally, the function ranks the documents based
        on their similarity scores and returns the ranked document identifiers
        and their scores.

        Parameters
        ----------
        query : str
            The input query for which relevant passages should be retrieved.

        Returns
        -------
        tuple : Tuple[np.ndarray, np.ndarray]
            A tuple containing two elements:
            - A list of sorted document identifiers based on their relevance scores.
            - A numpy array of the normalized similarity scores for the corresponding
              documents.
        """
        query_embedding = self.query_to_embedding['passage'].get(query, None)
        if query_embedding is None:
            query_embedding = self.embedding_model.batch_encode(query,
                                                                instruction=get_query_instruction('query_to_passage'),
                                                                norm=True)
        query_doc_scores = np.dot(self.passage_embeddings, query_embedding.T)
        query_doc_scores = np.squeeze(query_doc_scores) if query_doc_scores.ndim == 2 else query_doc_scores
        query_doc_scores = min_max_normalize(query_doc_scores)

        sorted_doc_ids = np.argsort(query_doc_scores)[::-1]
        sorted_doc_scores = query_doc_scores[sorted_doc_ids.tolist()]
        return sorted_doc_ids, sorted_doc_scores


    def get_top_k_weights(self,
                          link_top_k: int,
                          all_phrase_weights: np.ndarray,
                          linking_score_map: Dict[str, float]) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        This function filters the all_phrase_weights to retain only the weights for the
        top-ranked phrases in terms of the linking_score_map. It also filters linking scores
        to retain only the top `link_top_k` ranked nodes. Non-selected phrases in phrase
        weights are reset to a weight of 0.0.

        Args:
            link_top_k (int): Number of top-ranked nodes to retain in the linking score map.
            all_phrase_weights (np.ndarray): An array representing the phrase weights, indexed
                by phrase ID.
            linking_score_map (Dict[str, float]): A mapping of phrase content to its linking
                score, sorted in descending order of scores.

        Returns:
            Tuple[np.ndarray, Dict[str, float]]: A tuple containing the filtered array
            of all_phrase_weights with unselected weights set to 0.0, and the filtered
            linking_score_map containing only the top `link_top_k` phrases.
        """
        # choose top ranked nodes in linking_score_map
        linking_score_map = dict(sorted(linking_score_map.items(), key=lambda x: x[1], reverse=True)[:link_top_k])

        # only keep the top_k phrases in all_phrase_weights
        top_k_phrases = set(linking_score_map.keys())
        top_k_phrases_keys = set(
            [compute_mdhash_id(content=top_k_phrase, prefix="entity-") for top_k_phrase in top_k_phrases])

        for phrase_key in self.node_name_to_vertex_idx:
            if phrase_key not in top_k_phrases_keys:
                phrase_id = self.node_name_to_vertex_idx.get(phrase_key, None)
                if phrase_id is not None:
                    all_phrase_weights[phrase_id] = 0.0

        assert np.count_nonzero(all_phrase_weights) == len(linking_score_map.keys())
        return all_phrase_weights, linking_score_map

    def graph_search_with_fact_entities(self, query: str,
                                        link_top_k: int,
                                        query_fact_scores: np.ndarray,
                                        top_k_facts: List[Tuple],
                                        top_k_fact_indices: List[str],
                                        passage_node_weight: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes document scores based on fact-based similarity and relevance using personalized
        PageRank (PPR) and dense retrieval models. This function combines the signal from the relevant
        facts identified with passage similarity and graph-based search for enhanced result ranking.

        Parameters:
            query (str): The input query string for which similarity and relevance computations
                need to be performed.
            link_top_k (int): The number of top phrases to include from the linking score map for
                downstream processing.
            query_fact_scores (np.ndarray): An array of scores representing fact-query similarity
                for each of the provided facts.
            top_k_facts (List[Tuple]): A list of top-ranked facts, where each fact is represented
                as a tuple of its subject, predicate, and object.
            top_k_fact_indices (List[str]): Corresponding indices or identifiers for the top-ranked
                facts in the query_fact_scores array.
            passage_node_weight (float): Default weight to scale passage scores in the graph.

        Returns:
            Tuple[np.ndarray, np.ndarray]: A tuple containing two arrays:
                - The first array corresponds to document IDs sorted based on their scores.
                - The second array consists of the PPR scores associated with the sorted document IDs.
        """


        #Assigning phrase weights based on selected facts from previous steps.
        linking_score_map = {}  # from phrase to the average scores of the facts that contain the phrase
        phrase_scores = {}  # store all fact scores for each phrase regardless of whether they exist in the knowledge graph or not
        phrase_weights = np.zeros(len(self.graph.vs['name']))
        passage_weights = np.zeros(len(self.graph.vs['name']))

        for rank, f in enumerate(top_k_facts):
            subject_phrase = f[0].lower()
            predicate_phrase = f[1].lower()
            object_phrase = f[2].lower()
            fact_score = query_fact_scores[
                top_k_fact_indices[rank]] if query_fact_scores.ndim > 0 else query_fact_scores
            for phrase in [subject_phrase, object_phrase]:
                phrase_key = compute_mdhash_id(
                    content=phrase,
                    prefix="entity-"
                )
                phrase_id = self.node_name_to_vertex_idx.get(phrase_key, None)  #得到图中节点的下比标

                if phrase_id is not None:
                    phrase_weights[phrase_id] = fact_score

                    if len(self.ent_node_to_chunk_ids.get(phrase_key, set())) > 0:
                        phrase_weights[phrase_id] /= len(self.ent_node_to_chunk_ids[phrase_key])

                if phrase not in phrase_scores:
                    phrase_scores[phrase] = []
                phrase_scores[phrase].append(fact_score)

        # calculate average fact score for each phrase
        for phrase, scores in phrase_scores.items():
            linking_score_map[phrase] = float(np.mean(scores))

        if link_top_k:
            phrase_weights, linking_score_map = self.get_top_k_weights(link_top_k,
                                                                           phrase_weights,
                                                                           linking_score_map)  # at this stage, the length of linking_scope_map is determined by link_top_k

        #Get passage scores according to chosen dense retrieval model
        dpr_sorted_doc_ids, dpr_sorted_doc_scores = self.dense_passage_retrieval(query)
        normalized_dpr_sorted_scores = min_max_normalize(dpr_sorted_doc_scores)

        for i, dpr_sorted_doc_id in enumerate(dpr_sorted_doc_ids.tolist()):
            passage_node_key = self.passage_node_keys[dpr_sorted_doc_id]
            passage_dpr_score = normalized_dpr_sorted_scores[i]
            passage_node_id = self.node_name_to_vertex_idx[passage_node_key]
            passage_weights[passage_node_id] = passage_dpr_score * passage_node_weight
            passage_node_text = self.chunk_embedding_store.get_row(passage_node_key)["content"]
            linking_score_map[passage_node_text] = passage_dpr_score * passage_node_weight

        #Combining phrase and passage scores into one array for PPR
        node_weights = phrase_weights + passage_weights

        #Recording top 30 facts in linking_score_map
        if len(linking_score_map) > 30:
            linking_score_map = dict(sorted(linking_score_map.items(), key=lambda x: x[1], reverse=True)[:30])

        assert sum(node_weights) > 0, f'No phrases found in the graph for the given facts: {top_k_facts}'

        #Running PPR algorithm based on the passage and phrase weights previously assigned
        ppr_start = time.time()
        ppr_sorted_doc_ids, ppr_sorted_doc_scores = self.run_ppr(node_weights, damping=self.global_config.damping)
        ppr_end = time.time()

        self.ppr_time += (ppr_end - ppr_start)

        assert len(ppr_sorted_doc_ids) == len(
            self.passage_node_idxs), f"Doc prob length {len(ppr_sorted_doc_ids)} != corpus length {len(self.passage_node_idxs)}"

        return ppr_sorted_doc_ids, ppr_sorted_doc_scores

    
    def rerank_facts_copy(self, query: str, query_fact_scores: np.ndarray,paragraphs: List[str],tittles: List[str]) -> Tuple[List[int], List[Tuple], dict]:
        """

        Args:

        Returns:
            top_k_fact_indicies:
            top_k_facts:
            rerank_log (dict): {'facts_before_rerank': candidate_facts, 'facts_after_rerank': top_k_facts}
                - candidate_facts (list): list of link_top_k facts (each fact is a relation triple in tuple data type).
                - top_k_facts:


        """
        # load args
        link_top_k: int = self.global_config.linking_top_k

        candidate_fact_indices = np.argsort(query_fact_scores)[-40:][
                                ::-1].tolist()  # list of ranked link_top_k fact relative indices
        real_candidate_fact_ids = [self.fact_node_keys[idx] for idx in
                                candidate_fact_indices]  # list of ranked link_top_k fact keys
        fact_row_dict = self.fact_embedding_store.get_rows(real_candidate_fact_ids)
        candidate_facts_old = [eval(fact_row_dict[id]['content']) for id in real_candidate_fact_ids]  # list of link_top_k facts (each fact is a relation triple in tuple data type)
        candidate_fact_indices_new = []
        candidate_facts = []
        for index,id in enumerate(real_candidate_fact_ids):
            passage_ids = self.fact_to_chunk_ids[id]
            candidate_fact = eval(fact_row_dict[id]['content'])
            # print(candidate_fact)
            words = []
            for factt in candidate_fact:
                word = factt.split()
                words.append(word)
            for inde,paragraph in enumerate(paragraphs):
                scen = tittles[inde].lower()+paragraph.lower()
                flag = 0
                for zz in words:
                    cnt = 0
                    total_cnt =  len(zz)
                    if total_cnt ==0:
                        continue
                    for zy in zz:
                        if zy in scen:
                            cnt+=1
                    if cnt==total_cnt:
                        flag+=1
                if flag >=2:
                    candidate_facts.append(candidate_fact)
                    candidate_fact_indices_new.append(candidate_fact_indices[index])
                    break
    
        candidate_facts = candidate_facts[:link_top_k]
        candidate_fact_indices_new = candidate_fact_indices_new[:link_top_k]
        # print(paragraph)
        # print("candidate_facts_old")
        # print(candidate_facts_old)
        # print("candidate_fact_indices")
        # print(candidate_fact_indices)
        # print("candidate_facts")
        # print(candidate_facts)
        # print("candidate_fact_indices_new")
        # print(candidate_fact_indices_new)
        # print("过滤前")
        # print(candidate_facts)

        top_k_fact_indices, top_k_facts, reranker_dict,additonal_query = self.rerank_filter(query,
                                                                            candidate_facts,
                                                                            candidate_fact_indices_new,
                                                                            len_after_rerank=10)   #LLM过滤后的结果

        rerank_log = {'facts_before_rerank': candidate_facts, 'facts_after_rerank': top_k_facts}

        return top_k_fact_indices, top_k_facts, rerank_log,additonal_query
    def rerank_facts_copy_new(self, query: str, query_fact_scores: np.ndarray,paragraphs: List[str],tittles: List[str]) -> Tuple[List[int], List[Tuple], dict]:
        """

        Args:

        Returns:
            top_k_fact_indicies:
            top_k_facts:
            rerank_log (dict): {'facts_before_rerank': candidate_facts, 'facts_after_rerank': top_k_facts}
                - candidate_facts (list): list of link_top_k facts (each fact is a relation triple in tuple data type).
                - top_k_facts:
        """
        # load args
        link_top_k: int = self.global_config.linking_top_k

        candidate_fact_indices = np.argsort(query_fact_scores)[-100:][
                                ::-1].tolist()  # list of ranked link_top_k fact relative indices
        real_candidate_fact_ids = [self.fact_node_keys[idx] for idx in
                                candidate_fact_indices]  # list of ranked link_top_k fact keys
        fact_row_dict = self.fact_embedding_store.get_rows(real_candidate_fact_ids)
        candidate_facts_old = [eval(fact_row_dict[id]['content']) for id in real_candidate_fact_ids]  # list of link_top_k facts (each fact is a relation triple in tuple data type)
        # print("candidate_facts_old")
        # print(candidate_facts_old)
        candidate_fact_indices_new = []
        candidate_facts = []
        for index,id in enumerate(real_candidate_fact_ids):
            passages_ids = self.fact_to_chunk_ids[id]
            passages = self.chunk_embedding_store.get_rows(passages_ids)
            passs = [passages[rr]['content'] for  rr in passages_ids]
            candidate_fact = eval(fact_row_dict[id]['content'])
            # print("candidate_fact")
            # print(candidate_fact)
            # print("passages")
            # print(passs)
            # pp = set()

            for ined,passage in enumerate(passs):
                if passage in paragraphs:
                    candidate_facts.append(candidate_fact)
                    candidate_fact_indices_new.append(candidate_fact_indices[index])
            
                    # ids = self.chunk_embedding_store.get_hash_id(passage)
                    # pp.add(ids)
                    # break
            # if len(pp) >0:
            #     self.fact_to_chunk_ids[id] = pp
    
        candidate_facts = candidate_facts[:30]
        candidate_fact_indices_new = candidate_fact_indices_new[:30]
        # print("after")
        # print(candidate_facts)


        top_k_fact_indices, top_k_facts, reranker_dict,additonal_query = self.rerank_filter(query,
                                                                            candidate_facts,
                                                                            candidate_fact_indices_new,
                                                                            len_after_rerank=10)   #LLM过滤后的结果

        rerank_log = {'facts_before_rerank': candidate_facts, 'facts_after_rerank': top_k_facts}

        return top_k_fact_indices, top_k_facts, rerank_log, additonal_query
    

    def rerank_facts_gene_data_retri(self, query: str, query_fact_scores: np.ndarray,paragraphs: List[str],tittles: List[str],old_message: List[Dict[str, str]],old_facts: List[Tuple]) -> Tuple[List[int], List[Tuple], dict]:
        """

        Args:

        Returns:
            top_k_fact_indicies:
            top_k_facts:
            rerank_log (dict): {'facts_before_rerank': candidate_facts, 'facts_after_rerank': top_k_facts}
                - candidate_facts (list): list of link_top_k facts (each fact is a relation triple in tuple data type).
                - top_k_facts:
        """
        # load args

        candidate_fact_indices = np.argsort(query_fact_scores)[-500:][
                                ::-1].tolist()  # list of ranked link_top_k fact relative indices
        real_candidate_fact_ids = [self.fact_node_keys[idx] for idx in
                                candidate_fact_indices]  # list of ranked link_top_k fact keys
        fact_row_dict = self.fact_embedding_store.get_rows(real_candidate_fact_ids)
        candidate_facts_old = [eval(fact_row_dict[id]['content']) for id in real_candidate_fact_ids]  # list of link_top_k facts (each fact is a relation triple in tuple data type)

        # print(candidate_fact_indices)
        # print(real_candidate_fact_ids)
        # print(fact_row_dict)
        # print(candidate_facts_old)
        # exit(0)
        # print("candidate_facts_old")
        # print(candidate_facts_old)
        # print(len(candidate_facts_old))
        candidate_fact_indices_new = []
        candidate_facts = []
        for index,id in enumerate(real_candidate_fact_ids):
            passages_ids = self.fact_to_chunk_ids[id]
            passages = self.chunk_embedding_store.get_rows(passages_ids)
            passs = [passages[rr]['content'] for  rr in passages_ids]
            candidate_fact = eval(fact_row_dict[id]['content'])

            for ined,passage in enumerate(passs):
                if passage in paragraphs:
                    candidate_facts.append(candidate_fact)
                    candidate_fact_indices_new.append(candidate_fact_indices[index])

        combined = list(zip(candidate_facts, candidate_fact_indices_new))
        # print(candidate_fact_indices_new)

        random.shuffle(combined)
        
        if len(combined) > 0:
            # 只有当列表不为空时，才进行解包
            candidate_facts, candidate_fact_indices_new = zip(*combined)
            
            # 注意：zip 解包后是元组(tuple)，如果你后面需要追加元素，最好转回 list
            candidate_facts = list(candidate_facts)
            candidate_fact_indices_new = list(candidate_fact_indices_new)
        else:
            # 如果列表为空，保持它们为空列表，防止报错
            candidate_facts = []
            candidate_fact_indices_new = []

        # print(candidate_fact_indices_new)
    
        # candidate_facts = candidate_facts[:30]
        # candidate_fact_indices_new = candidate_fact_indices_new[:30]
        # print("after")
        # print(candidate_facts)
        # print(len(candidate_facts))
        # exit(0)


        top_k_fact_indices, top_k_facts, reranker_dict,additonal_query,thought,input_token_count,output_token_count = self.rerank_filter_gene_data(query,
                                                                            candidate_facts,
                                                                            candidate_fact_indices_new,
                                                                            old_message,
                                                                            len_after_rerank=10)   #LLM过滤后的结果


        # if top_k_facts and old_facts:
        #     all_in_old = all(fact in old_facts for fact in top_k_facts)
        #     if all_in_old:
        #         for cfact in candidate_facts:
        #             if cfact not in old_facts:
        #                 top_k_facts.append(cfact)
        #                 print("zzzzz1")
        #                 break
        # print("111")



        if not top_k_facts:
            for ccfact in candidate_facts:
                if ccfact not in old_facts:
                    top_k_facts.append(ccfact)
                    print("zzzzz2")
                    break

        matches = re.findall(r'\[(.*?)\]', thought)
        # print(matches)
        for ma in matches:
            closest_matched_fact = difflib.get_close_matches(str(ma), [str(i) for i in candidate_facts], n=1, cutoff=0.0)
            if closest_matched_fact:
                closest_matched_fact = closest_matched_fact[0]
                closest_matched_fact = ast.literal_eval(closest_matched_fact)
            # print(closest_matched_fact)
                if closest_matched_fact not in top_k_facts:
                    top_k_facts.append(closest_matched_fact)
                    print("zzzzz3")



        rerank_log = {'facts_before_filter': candidate_facts, 'thought': thought ,'facts_after_filter': top_k_facts}
        return top_k_fact_indices, top_k_facts, rerank_log, additonal_query,input_token_count,output_token_count

    def rerank_facts_gene_data(self, query: str, query_fact_scores: np.ndarray,paragraphs: List[str],tittles: List[str],old_message: List[Dict[str, str]],old_facts: List[Tuple]) -> Tuple[List[int], List[Tuple], dict]:
        """

        Args:

        Returns:
            top_k_fact_indicies:
            top_k_facts:
            rerank_log (dict): {'facts_before_rerank': candidate_facts, 'facts_after_rerank': top_k_facts}
                - candidate_facts (list): list of link_top_k facts (each fact is a relation triple in tuple data type).
                - top_k_facts:
        """
        # load args
        link_top_k: int = self.global_config.linking_top_k

        candidate_fact_indices = np.argsort(query_fact_scores)[-200:][
                                ::-1].tolist()  # list of ranked link_top_k fact relative indices
        real_candidate_fact_ids = [self.fact_node_keys[idx] for idx in
                                candidate_fact_indices]  # list of ranked link_top_k fact keys
        fact_row_dict = self.fact_embedding_store.get_rows(real_candidate_fact_ids)
        candidate_facts_old = [eval(fact_row_dict[id]['content']) for id in real_candidate_fact_ids]  # list of link_top_k facts (each fact is a relation triple in tuple data type)

        # print(candidate_fact_indices)
        # print(real_candidate_fact_ids)
        # print(fact_row_dict)
        # print(candidate_facts_old)
        # exit(0)
        # print("candidate_facts_old")
        # print(candidate_facts_old)
        # print(len(candidate_facts_old))
        candidate_fact_indices_new = []
        candidate_facts = []
        for index,id in enumerate(real_candidate_fact_ids):
            passages_ids = self.fact_to_chunk_ids[id]
            passages = self.chunk_embedding_store.get_rows(passages_ids)
            passs = [passages[rr]['content'] for  rr in passages_ids]
            candidate_fact = eval(fact_row_dict[id]['content'])

            for ined,passage in enumerate(passs):
                if passage in paragraphs:
                    candidate_facts.append(candidate_fact)
                    candidate_fact_indices_new.append(candidate_fact_indices[index])

    
        candidate_facts = candidate_facts[:10]
        candidate_fact_indices_new = candidate_fact_indices_new[:10]
        # print("after")
        # print(candidate_facts)
        # print(len(candidate_facts))
        # exit(0)


        top_k_fact_indices, top_k_facts, reranker_dict,additonal_query,thought,input_token_count,output_token_count = self.rerank_filter_gene_data(query,
                                                                            candidate_facts,
                                                                            candidate_fact_indices_new,
                                                                            old_message,
                                                                            len_after_rerank=10)   #LLM过滤后的结果


        # if top_k_facts and old_facts:
        #     all_in_old = all(fact in old_facts for fact in top_k_facts)
        #     if all_in_old:
        #         for cfact in candidate_facts:
        #             if cfact not in old_facts:
        #                 top_k_facts.append(cfact)
        #                 print("zzzzz1")
        #                 break
        # print("111")



        if not top_k_facts:
            for ccfact in candidate_facts:
                if ccfact not in old_facts:
                    top_k_facts.append(ccfact)
                    print("zzzzz2")
                    break

        matches = re.findall(r'\[(.*?)\]', thought)
        # print(matches)
        for ma in matches:
            closest_matched_fact = difflib.get_close_matches(str(ma), [str(i) for i in candidate_facts], n=1, cutoff=0.0)
            if closest_matched_fact:
                closest_matched_fact = closest_matched_fact[0]
                closest_matched_fact = ast.literal_eval(closest_matched_fact)
            # print(closest_matched_fact)
                if closest_matched_fact not in top_k_facts:
                    top_k_facts.append(closest_matched_fact)
                    print("zzzzz3")



        rerank_log = {'facts_before_filter': candidate_facts, 'thought': thought ,'facts_after_filter': top_k_facts}

        return top_k_fact_indices, top_k_facts, rerank_log, additonal_query,input_token_count,output_token_count