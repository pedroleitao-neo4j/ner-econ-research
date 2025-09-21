import os, io
import conllu
from dataclasses import dataclass
from typing import List, Dict
import numpy as np
import logging
from datasets import Dataset, DatasetDict
from transformers import (AutoTokenizer, AutoModelForTokenClassification,
                          DataCollatorForTokenClassification, TrainingArguments,
                          Trainer, pipeline, set_seed)
from seqeval.metrics import f1_score, precision_score, recall_score, classification_report
import argparse

class NERTrainer:
    def __init__(self, args):
        self.args = args
        self.label_list = None
        self.label_to_id = None
        self.id_to_label = None
        self.tokenizer = None
        self.tokenized_datasets = None
        self.model = None
        self.trainer = None
        
        # Set up logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Create console handler with formatting
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        set_seed(self.args.seed)

    def load_data(self):
        DATA = {
            "train": self.args.train_file,
            "validation": self.args.validation_file,
            "test": self.args.test_file
        }
        ds = DatasetDict({
            split: self._load_conll_dataset(path) for split, path in DATA.items()
        })
        
        label_set = set()
        for ex in ds["train"]:
            label_set.update(ex["labels"])
        self.label_list = sorted(label_set)
        self.label_to_id = {l: i for i, l in enumerate(self.label_list)}
        self.id_to_label = {i: l for l, i in self.label_to_id.items()}
        
        return ds

    def _load_conll_dataset(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = ""
            for line in f:
                if line.strip():
                    data += line.replace(" ", "\t", 1)
                else:
                    data += line
        
        sentences = conllu.parse(data, fields=["form", "ner"])
        
        tokens_list = []
        labels_list = []
        
        for sentence in sentences:
            tokens = [token["form"] for token in sentence]
            labels = [token["ner"] for token in sentence]
            tokens_list.append(tokens)
            labels_list.append(labels)
            
        return Dataset.from_dict({"tokens": tokens_list, "labels": labels_list})

    def prepare_tokenizer(self):
        self.tokenizer = AutoTokenizer.from_pretrained(self.args.model_name, use_fast=True)

    def tokenize_and_align_data(self, ds):
        def align_labels_with_tokens(labels: List[str], word_ids: List[int]):
            aligned = []
            prev = None
            for wid in word_ids:
                if wid is None:
                    aligned.append(-100)
                elif wid != prev:
                    aligned.append(self.label_to_id[labels[wid]])
                else:
                    aligned.append(-100)
                prev = wid
            return aligned

        def tokenize_batch(batch):
            tokenized = self.tokenizer(batch["tokens"], is_split_into_words=True,
                            truncation=True, max_length=self.args.max_length)
            tokenized["labels"] = []
            for i, labels in enumerate(batch["labels"]):
                word_ids = tokenized.word_ids(i)
                tokenized["labels"].append(align_labels_with_tokens(labels, word_ids))
            return tokenized

        self.tokenized_datasets = ds.map(tokenize_batch, batched=True, remove_columns=ds["train"].column_names)

    def initialize_model(self):
        self.model = AutoModelForTokenClassification.from_pretrained(
            self.args.model_name,
            num_labels=len(self.label_list),
            id2label=self.id_to_label,
            label2id=self.label_to_id
        )

    def _compute_metrics(self, p):
        preds = np.argmax(p.predictions, axis=2)
        labels = p.label_ids

        true_preds, true_labels = [], []
        for pred, lab in zip(preds, labels):
            p_i, l_i = [], []
            for p_id, l_id in zip(pred, lab):
                if l_id == -100:
                    continue
                p_i.append(self.id_to_label[p_id])
                l_i.append(self.id_to_label[l_id])
            true_preds.append(p_i); true_labels.append(l_i)
        return {
            "precision": precision_score(true_labels, true_preds),
            "recall": recall_score(true_labels, true_preds),
            "f1": f1_score(true_labels, true_preds),
            "report": classification_report(true_labels, true_preds, zero_division=0)
        }

    def train_model(self):
        training_args = TrainingArguments(
            output_dir=self.args.output_dir,
            per_device_train_batch_size=self.args.batch,
            per_device_eval_batch_size=self.args.batch,
            learning_rate=self.args.lr,
            num_train_epochs=self.args.epochs,
            weight_decay=self.args.weight_decay,
            warmup_ratio=self.args.warmup_ratio,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            greater_is_better=True,
            logging_steps=self.args.log_steps,
            report_to="none",
            fp16=False,
        )

        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=self.tokenized_datasets["train"],
            eval_dataset=self.tokenized_datasets["validation"],
            tokenizer=self.tokenizer,
            data_collator=DataCollatorForTokenClassification(self.tokenizer),
            compute_metrics=self._compute_metrics
        )

        self.trainer.train()
        self.trainer.save_model(training_args.output_dir)
        self.tokenizer.save_pretrained(training_args.output_dir)

    def evaluate(self):
        self.logger.info(self.trainer.evaluate(self.tokenized_datasets["test"]).get("eval_report", ""))

    def run_inference(self):
        ner = pipeline("ner", model=self.args.output_dir, tokenizer=self.args.output_dir, aggregation_strategy="simple")
        self.logger.info(ner(self.args.run_example))

    def run(self):
        ds = self.load_data()
        self.prepare_tokenizer()
        self.tokenize_and_align_data(ds)
        self.initialize_model()
        self.train_model()
        self.evaluate()
        self.run_inference()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='''
                                     Train NER model with HuggingFace Transformers. Data should be in CoNLL format, and use BIO tagging scheme.
                                     Any pretrained transformer model from HuggingFace should work fine, for example:
                                        - microsoft/mdeberta-v3-base
                                        - bert-base-cased
                                        - roberta-base
                                        - google/electra-base-discriminator
                                     ''')

    parser.add_argument("--model_name", type=str, default="microsoft/mdeberta-v3-base")
    parser.add_argument("--train_file", type=str, default="data/econ_ie/train.conll")
    parser.add_argument("--validation_file", type=str, default="data/econ_ie/dev.conll")
    parser.add_argument("--test_file", type=str, default="data/econ_ie/test.conll")
    parser.add_argument("--output_dir", type=str, default="mdeberta-v3-econ-ie-ner-tuned")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_length", type=int, default=512)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--warmup_ratio", type=float, default=0.1)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--log_steps", type=int, default=50)
    parser.add_argument("--run_example", type=str, help="Run example inference after training.", default="Raising interest rates impacted the ability of young people to buy homes.")

    args = parser.parse_args()
    
    trainer = NERTrainer(args)
    trainer.run()

