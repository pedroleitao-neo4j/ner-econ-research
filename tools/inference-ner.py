import argparse
import json
import logging
import pandas as pd
import torch
from tqdm import tqdm
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
from collections import Counter

class NERInference:
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)
        self.tokenizer = AutoTokenizer.from_pretrained(self.args.model_path)
        self.model = AutoModelForTokenClassification.from_pretrained(self.args.model_path)
        
        # Set device
        device = 0 if torch.cuda.is_available() else -1
        
        self.ner_pipeline = pipeline(
            "ner", 
            model=self.model, 
            tokenizer=self.tokenizer, 
            aggregation_strategy="simple",
            device=device,
            batch_size=self.args.batch_size
        )

    def load_data(self):
        if self.args.input_file.endswith('.csv'):
            df = pd.read_csv(self.args.input_file)
        elif self.args.input_file.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(self.args.input_file)
        else:
            raise ValueError("Unsupported input file format. Please use CSV or Excel.")

        if self.args.text_column not in df.columns:
            raise ValueError(f"Text column '{self.args.text_column}' not found in the input file.")
        
        self.logger.info(f"Loaded data from {self.args.input_file} with {len(df)} rows")
        return df

    def extract_entities(self, texts):
        self.logger.info(f"Processing {len(texts)} texts with batch size {self.args.batch_size}")
        
        # Use the pipeline directly with all texts - it will handle batching internally
        results = []
        for result in tqdm(self.ner_pipeline(texts), total=len(texts), desc="Processing texts"):
            results.append(result)
        
        return results

    def save_results(self, df, results):
        filtered_entities_list = []
        entity_group_counts = Counter()
        for entities in results:
            current_entities = []
            for entity in entities:
                if entity['score'] >= self.args.min_score:
                    # Filter by entity type if entities_to_keep is specified
                    if self.args.entities_to_keep is None or entity['entity_group'] in self.args.entities_to_keep:
                        # Convert numpy.float32 to float for JSON serialization
                        entity['score'] = float(entity['score'])

                        # Split entities that contain semicolons
                        if ';' in entity['word']:
                            sub_words = [word.strip() for word in entity['word'].split(';') if word.strip()]
                            for sub_word in sub_words:
                                new_entity = {
                                    'entity_group': entity['entity_group'],
                                    'score': entity['score'],
                                    'word': sub_word
                                }
                                current_entities.append(new_entity)
                                entity_group_counts[new_entity['entity_group']] += 1
                        else:
                            current_entities.append(entity)
                            entity_group_counts[entity['entity_group']] += 1

            filtered_entities_list.append(current_entities)

        # Check if entities column already exists and merge if it does
        if self.args.entities_column in df.columns:
            for i, new_entities in enumerate(filtered_entities_list):
                existing_entities = df.iloc[i][self.args.entities_column]
                if isinstance(existing_entities, str):
                    try:
                        existing_entities = json.loads(existing_entities)
                    except:
                        existing_entities = []
                elif not isinstance(existing_entities, list):
                    existing_entities = []

                # Merge existing entities (unfiltered) with new filtered entities
                filtered_entities_list[i] = existing_entities + new_entities

        df[self.args.entities_column] = filtered_entities_list

        if self.args.output_file.endswith('.csv'):
            df[self.args.entities_column] = df[self.args.entities_column].apply(json.dumps)
            df.to_csv(self.args.output_file, index=False)
        elif self.args.output_file.endswith('.json'):
            df.to_json(self.args.output_file, orient='records', lines=True, indent=4)
        else:
            self.logger.warning("Unsupported output file format. Saving as CSV.")
            df['entities'] = df['entities'].apply(json.dumps)
            df.to_csv(self.args.output_file, index=False)

        # Log entity group counts for this run
        if entity_group_counts:
            self.logger.info("Entity group counts (this run):")
            for group, count in entity_group_counts.most_common():
                self.logger.info(f"{group}: {count}")
            self.logger.info(f"Total entities extracted (this run): {sum(entity_group_counts.values())}")
        else:
            self.logger.info("No entities extracted (this run).")

        self.logger.info(f"Inference complete. Results saved to {self.args.output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract entities from a text file using a fine-tuned NER model.")
    parser.add_argument("input_file", help="Path to the input file (CSV or Excel).")
    parser.add_argument("output_file", help="Path to save the output file with entities (CSV or JSON).")
    parser.add_argument("--model_path", default="mdeberta-v3-econ-ie-ner-tuned", help="Path to the fine-tuned model directory.")
    parser.add_argument("--text_column", default="text", help="Name of the column containing the text to process.")
    parser.add_argument("--entities_column", default="entities", help="Name of the column to store extracted entities.")
    parser.add_argument("--entities_to_keep", nargs='+', default=None, help="List of entity types to keep. If not specified, all entities are kept.")
    parser.add_argument("--min_score", type=float, default=0.8, help="Minimum score for an entity to be included.")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size for processing texts.")
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set the logging level.")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting NER inference")
        inference_engine = NERInference(args)
        df = inference_engine.load_data()
        texts = df[args.text_column].tolist()
        logger.info(f"Processing {len(texts)} texts")
        results = inference_engine.extract_entities(texts)
        inference_engine.save_results(df, results)
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Error: {e}")