import json
from DataProcess.Hotpotqa import HotpotQA

class Dataset:
    """
    Base class for datasets. 
    It can be extended to incorporate multi-agent tasks and reasoning pipelines.
    """
    name = "Dataset"

    def __init__(self):
        pass

class HotpotqaDataset:
    """
    HotpotqaDataset is a specific dataset class for handling HotpotQA samples. 
    It loads the original data from a JSON file, converts each sample into a 
    HotpotQA object, and provides an interface that can integrate into the 
    multi-agent reasoning pipeline.
    """
    name = "HotpotqaDataset"

    def __init__(self, dataset_path):
        """
        :param dataset_path: Path to a JSON file containing HotpotQA-format data.
        Initializes self.origin_datas and creates self.tasks as a list of HotpotQA instances.
        """
        self.origin_datas = self.load_json(dataset_path)
        self.tasks = [HotpotQA(datas) for datas in self.origin_datas]

    def load_json(self, dataset_path):
        """
        Loads raw data from the specified JSON file.
        :param dataset_path: The path to the JSON file containing HotpotQA data.
        :return: A list of dictionaries where each element represents a HotpotQA item.
        """
        with open(dataset_path, 'r') as file:
            origin_datas = json.load(file)
        return origin_datas

    def __len__(self):
        """
        Returns the length of the dataset, corresponding to the total number of tasks.
        """
        return len(self.tasks)
