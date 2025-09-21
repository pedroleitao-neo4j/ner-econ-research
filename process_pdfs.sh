#!/bin/sh
#
# Assumes you have created the conda environment `econ-ie` with:
#
# conda env create -f environment.yml
#
# And activated it with:
#
# conda activate econ-ie
#
python -m spacy download en_core_web_sm
python pdf_parser.py --pdf_dir pdfs --output_csv results/all_pdfs.csv --min_chars 60 --max_sents 1
python inference-ner.py results/all_pdfs.csv results/all_pdfs_inferred.csv --model_path models/econberta-fs-econ-ie-ner-tuned --text_column textBlock --min_score 0.9
#python inference-ner.py results/all_pdfs_inferred.csv results/all_pdfs_inferred.csv --model_path dslim/bert-large-NER --text_column textBlock --min_score 0.9 --entities_to_keep PER ORG LOC
python inference-ner.py results/all_pdfs_inferred.csv results/all_pdfs_inferred.csv --model_path Gladiator/microsoft-deberta-v3-large_ner_conll2003 --text_column textBlock --min_score 0.9 --entities_to_keep PER ORG LOC
python relate.py --input_csv results/all_pdfs_inferred.csv --output_csv results/all_pdfs_related.csv --attach_outcome_population
python skos_alternatives.py --input_csv results/all_pdfs_related.csv --columns org loc subject_text --skos rdf/eurovoc_in_skos_core_concepts.rdf --output_csv results/all_pdfs_related_alternatives.csv
python to_neo4j.py --input_csv results/all_pdfs_related_alternatives.csv --output_cypher results/all_pdfs_related_alternatives.cypher --alternative_suffix _alternative --add_alternative_columns org loc per subject_text --alternative_relationship HAS_ALTERNATIVE
