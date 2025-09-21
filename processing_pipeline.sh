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
python tools/pdf_parser.py --pdf_dir pdfs --output_csv results/all_pdfs.csv --min_chars 60 --max_sents 1
python tools/inference-ner.py results/all_pdfs.csv results/all_pdfs_inferred.csv --model_path models/econberta-fs-econ-ie-ner-tuned --text_column textBlock --min_score 0.9
python tools/inference-ner.py results/all_pdfs_inferred.csv results/all_pdfs_inferred.csv --model_path Gladiator/microsoft-deberta-v3-large_ner_conll2003 --text_column textBlock --min_score 0.9 --entities_to_keep PER ORG LOC
python tools/relate.py --input_csv results/all_pdfs_inferred.csv --output_csv results/all_pdfs_related.csv --attach_outcome_population
python tools/skos_alternatives.py --input_csv results/all_pdfs_related.csv --columns org loc subject_text --skos 'https://op.europa.eu/o/opportal-service/euvoc-download-handler?cellarURI=http%3A%2F%2Fpublications.europa.eu%2Fresource%2Fdistribution%2Feurovoc%2F20250702-0%2Fzip%2Fskos_xl%2Feurovoc_skos.zip&fileName=eurovoc_skos.zip' --output_csv results/all_pdfs_related_alternatives.csv
python tools/to_neo4j.py --input_csv results/all_pdfs_related_alternatives.csv --output_cypher results/all_pdfs_related_alternatives.cypher --alternative_suffix _alternative --add_alternative_columns org loc per subject_text --alternative_relationship ALTERNATIVE_VOCABULARY
