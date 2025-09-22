#!/bin/sh
set -eu

# Assumes you have created the conda environment `econ-ie` with:
#   conda env create -f environment.yml
# And activated it with:
#   conda activate econ-ie

# -------------------------
# Configuration (overridable via env)
# -------------------------
PDF_DIR="${PDF_DIR:-pdfs}"
RESULTS_DIR="${RESULTS_DIR:-results}"

ALL_PDFS="$RESULTS_DIR/all_pdfs.csv"
INFERRED="$RESULTS_DIR/all_pdfs_inferred.csv"
RELATED="$RESULTS_DIR/all_pdfs_related.csv"
RELATED_ALT="$RESULTS_DIR/all_pdfs_related_alternatives.csv"
CYPHER="$RESULTS_DIR/all_pdfs_related_alternatives.cypher"

NER_MODEL_CUSTOM="${NER_MODEL_CUSTOM:-models/econberta-fs-econ-ie-ner-tuned}"
NER_MODEL_DEBERTA="${NER_MODEL_DEBERTA:-Gladiator/microsoft-deberta-v3-large_ner_conll2003}"

MIN_CHARS="${MIN_CHARS:-60}"
MAX_SENTS="${MAX_SENTS:-1}"
MIN_SCORE="${MIN_SCORE:-0.9}"
ENTITIES_TO_KEEP="${ENTITIES_TO_KEEP:-PER ORG LOC}"

SKOS_URL="${SKOS_URL:-https://op.europa.eu/o/opportal-service/euvoc-download-handler?cellarURI=http%3A%2F%2Fpublications.europa.eu%2Fresource%2Fdistribution%2Feurovoc%2F20250702-0%2Fzip%2Fskos_xl%2Feurovoc_skos.zip&fileName=eurovoc_skos.zip}"

TAXONOMY_COLUMNS="${TAXONOMY_COLUMNS:-org loc subject_text}"
ALT_SUFFIX="${ALT_SUFFIX:-_alternative}"
ALT_COLUMNS="${ALT_COLUMNS:-org loc per subject_text}"
ALT_RELATIONSHIP="${ALT_RELATIONSHIP:-ALTERNATIVE_VOCABULARY}"

# -------------------------
# Helpers
# -------------------------
run() {
  echo
  echo "==> $*"
  "$@"
}

# -------------------------
# Prep
# -------------------------
[ -d "$PDF_DIR" ] || { echo "Error: PDF_DIR not found: $PDF_DIR" >&2; exit 1; }
mkdir -p "$RESULTS_DIR"

# -------------------------
# Pipeline
# -------------------------
# 1) Ensure spaCy model is available
run python -m spacy download en_core_web_sm

# 2) Parse PDFs
run python tools/pdf_parser.py \
  --pdf_dir "$PDF_DIR" \
  --output_csv "$ALL_PDFS" \
  --min_chars "$MIN_CHARS" \
  --max_sents "$MAX_SENTS"

# 3) Domain NER
run python tools/inference-ner.py \
  "$ALL_PDFS" "$INFERRED" \
  --model_path "$NER_MODEL_CUSTOM" \
  --text_column textBlock \
  --min_score "$MIN_SCORE"

# 4) General NER (CONLL) with entity filtering
run python tools/inference-ner.py \
  "$INFERRED" "$INFERRED" \
  --model_path "$NER_MODEL_DEBERTA" \
  --text_column textBlock \
  --min_score "$MIN_SCORE" \
  --entities_to_keep $ENTITIES_TO_KEEP

# 5) Build relations
run python tools/relate.py \
  --input_csv "$INFERRED" \
  --output_csv "$RELATED" \
  --attach_outcome_population

# 6) Enrich with SKOS taxonomy
run python tools/skos_taxonomy.py \
  --input_csv "$RELATED" \
  --columns $TAXONOMY_COLUMNS \
  --skos "$SKOS_URL" \
  --output_csv "$RELATED_ALT"

# 7) Export to Neo4j Cypher
run python tools/to_neo4j.py \
  --input_csv "$RELATED_ALT" \
  --output_cypher "$CYPHER" \
  --alternative_suffix "$ALT_SUFFIX" \
  --add_alternative_columns $ALT_COLUMNS \
  --alternative_relationship "$ALT_RELATIONSHIP"

echo
echo "Done. Results in: $RESULTS_DIR"
