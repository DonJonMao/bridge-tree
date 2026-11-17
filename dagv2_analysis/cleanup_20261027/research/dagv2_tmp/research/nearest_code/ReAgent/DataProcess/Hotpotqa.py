import json
from DataProcess.Document import Document

class HotpotQA:
    """
    HotpotQA is a wrapper for items in the HotpotQA dataset. It contains:
    - question
    - answer
    - context (a list of documents)
    - supporting facts (relevant facts for multi-hop reasoning)
    """

    name = "HotpotQA"

    def __init__(self, data):
        """
        :param data: A dictionary representing a single HotpotQA sample,
                     containing question, answer, context, supporting_facts, etc.
        """
        self.data = data
        self.id = data['_id']
        self.type = data['type']
        self.level = data['level']
        self.question = data['question']
        self.answer = data['answer']
        self.context = data['context']
        self.documents = self.dealContext()
        self.supporting_facts = data['supporting_facts']

    def dealContext(self):
        """
        Iterates over the 'context' field and converts it into a list of Document objects.
        Each Document has a title and a list of paragraphs or sentences as context.
        """
        documents = []
        for paper in self.context:
            doc = Document(title=paper[0], context=paper[1])
            documents.append(doc)
        return documents

    def dealFacts(self):
        """
        Utilizes 'supporting_facts' to extract the relevant segments from the documents,
        providing a list of [title, fact_text].
        """
        titles = [doc.title for doc in self.documents]
        facts = []
        for fact in self.supporting_facts:
            fact_title = fact[0]
            fact_index = fact[1]
            title_index = titles.index(fact_title)
            fact_context = self.documents[title_index].context[fact_index]
            facts.append([fact_title, fact_context])
        return facts

    def __str__(self):
        """
        Constructs a string representation of all documents and their contexts,
        concatenating titles and paragraph lists.
        """
        knowledges = ""
        documents = self.documents
        for doc in documents:
            knowledge = f"{doc.title}\n" + "\n-".join(doc.context)
            knowledges += knowledge
        return knowledges

    def get_knowledge(self, args):
        """
        Returns the string representation of documents.
        If args.retrieval is False, it returns all knowledge.
        Otherwise, it still returns the entire content.
        """
        if not args.retrieval:
            return self.__str__()
        else:
            return self.__str__()
