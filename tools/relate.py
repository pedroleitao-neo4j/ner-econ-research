import csv
import json
import argparse
import re
import logging
from ast import literal_eval
from typing import List, Dict, Any, Iterable, Tuple, Optional

class CSVTripletExtractor:
    """
        Reads a CSV with columns:
            file,page,title,author,modDate,creationDate,subject,textBlock,entities

    The 'entities' column contains a JSON array of dicts:
      [{"entity_group": "...", "word": "...", "score": 0.99, "start": 10, "end": 20}, ...]

    Produces a triplets CSV with columns:
      file,title,subject_text,subject_type,relation,object_text,object_type,effect_size,avg_confidence,textBlock

    Rules:
      - For each intervention I and outcome O: (I)-[impacts]->(O)
        * Attach first found effect_size (if present in the same row).
      - For each intervention I and population P: (I)-[applies_to]->(P)
      - (Optional bonus) Outcome O to Population P: (O)-[experienced_by]->(P) if enabled.
    """

    def __init__(
        self,
        input_csv: str,
        output_csv: str,
        min_score: float = 0.0,
        attach_outcome_population: bool = False,
        keep_first_effect_only: bool = True,
    ):
        self.input_csv = input_csv
        self.output_csv = output_csv
        self.min_score = float(min_score)
        self.attach_outcome_population = bool(attach_outcome_population)
        self.keep_first_effect_only = bool(keep_first_effect_only)

        # Valid groups we care about for triplet generation
        self.PICO_GROUPS = {"population", "intervention", "outcome", "effect_size"}
        
        # Track all entity types found in the data
        self.all_entity_types = set()

        # Precompiled regex to normalize percent-like effect sizes
        self.percent_like = re.compile(r"\b\d+(\.\d+)?\s?%")
        
        # Set up logger
        self.logger = logging.getLogger(__name__)

    # Utilities
    def _normalize_text(self, s: str) -> str:
        if s is None:
            return ""
        # Collapse whitespace and strip quotes
        s = re.sub(r"\s+", " ", str(s)).strip().strip('“”"\'`‘’')
        return s

    def _parse_entities(self, raw: str) -> List[Dict[str, Any]]:
        """
        Parse the 'entities' field robustly:
        - Prefer json.loads
        - Fallback to ast.literal_eval
        - Return [] on failure or if not a list
        """
        if raw is None:
            return []
        txt = raw.strip()
        if not txt:
            return []
        try:
            data = json.loads(txt)
            self.logger.debug(f"Successfully parsed entities using json.loads: {len(data) if isinstance(data, list) else 'non-list'}")
        except Exception as e:
            self.logger.debug(f"json.loads failed, trying ast.literal_eval: {e}")
            try:
                data = literal_eval(txt)
                self.logger.debug(f"Successfully parsed entities using ast.literal_eval: {len(data) if isinstance(data, list) else 'non-list'}")
            except Exception as e2:
                self.logger.warning(f"Failed to parse entities field: {e2}")
                return []

        if not isinstance(data, list):
            self.logger.warning(f"Entities field is not a list, got {type(data)}")
            return []
        # Keep only dicts and expected keys
        out = []
        for e in data:
            if not isinstance(e, dict):
                continue
            eg = self._normalize_text(e.get("entity_group", ""))
            w  = self._normalize_text(e.get("word", ""))
            sc = float(e.get("score", 0.0)) if e.get("score") is not None else 0.0
            if eg and w:
                out.append({"entity_group": eg.lower(), "word": w, "score": sc})
        self.logger.debug(f"Extracted {len(out)} valid entities from {len(data)} raw entities")
        return out

    def _filter_by_score(self, ents: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.min_score <= 0.0:
            return list(ents)
        filtered = [e for e in ents if float(e.get("score", 0.0)) >= self.min_score]
        original_count = len(list(ents)) if hasattr(ents, '__len__') else sum(1 for _ in ents)
        self.logger.debug(f"Filtered entities by score >= {self.min_score}: {len(filtered)}/{original_count} kept")
        return filtered

    def _collect_by_group(self, ents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        bucket: Dict[str, List[Dict[str, Any]]] = {g: [] for g in self.PICO_GROUPS}
        other_bucket: Dict[str, List[Dict[str, Any]]] = {}
        
        for e in ents:
            g = e.get("entity_group", "").lower()
            self.all_entity_types.add(g)  # Track all entity types
            
            if g in bucket:
                bucket[g].append(e)
            else:
                # Collect other entity types
                if g not in other_bucket:
                    other_bucket[g] = []
                other_bucket[g].append(e)
        
        # Merge other entities into the main bucket
        bucket.update(other_bucket)
        return bucket

    def _collect_other_entities(self, buckets: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
        """
        Collect entities that are not part of PICO groups and format them for CSV columns.
        Returns a dict with entity_type -> comma-separated entity words.
        """
        other_entities = {}
        for entity_type, entities in buckets.items():
            if entity_type not in self.PICO_GROUPS and entities:
                # Collect unique words for this entity type
                words = list(dict.fromkeys([e["word"] for e in entities if e.get("word")]))
                if words:
                    other_entities[entity_type] = "; ".join(words)
        return other_entities

    def _pick_effect_sizes(self, effects: List[Dict[str, Any]]) -> Optional[str]:
        if not effects:
            return None
        # Try to find something that looks like a % first (e.g., "65% to 74%", "40% to 50%")
        # If multiple, join or take first depending on config.
        values = []
        for e in effects:
            w = e.get("word", "")
            if not w:
                continue
            # Simple normalization: extract % substrings; if none found, keep the full word.
            matches = self.percent_like.findall(w)
            if matches:
                values.append(self._normalize_text(w))
            else:
                values.append(self._normalize_text(w))
        if not values:
            return None
        if self.keep_first_effect_only:
            return values[0]
        return "; ".join(dict.fromkeys(values))  # dedup while preserving order

    def _avg_confidence(self, items: List[Dict[str, Any]]) -> float:
        if not items:
            return 0.0
        return sum(float(i.get("score", 0.0)) for i in items) / len(items)

    #
    # Core extraction per row
    #
    def _triplets_from_row(
        self,
        row: Dict[str, Any],
    ) -> Iterable[Dict[str, Any]]:
        """
        Yield triplet dicts with:
          subject_text, subject_type, relation, object_text, object_type, effect_size, avg_confidence
          + other entity columns
        """
        ents = self._parse_entities(row.get("entities"))
        ents = self._filter_by_score(ents)
        buckets = self._collect_by_group(ents)

        ints = buckets.get("intervention", [])
        outs = buckets.get("outcome", [])
        pops = buckets.get("population", [])
        effs = buckets.get("effect_size", [])

        # Collect other entities
        other_entities = self._collect_other_entities(buckets)
        
        pico_counts = f"interventions: {len(ints)}, outcomes: {len(outs)}, populations: {len(pops)}, effects: {len(effs)}"
        other_counts = f"other entities: {len(other_entities)} types"
        self.logger.debug(f"Row entities - {pico_counts}, {other_counts}")

        effect = self._pick_effect_sizes(effs)
        triplet_count = 0

        # I -> O (impacts)
        for i in ints:
            for o in outs:
                triplet_count += 1
                triplet = {
                    "subject_text": i["word"],
                    "subject_type": "intervention",
                    "relation": "impacts",
                    "object_text": o["word"],
                    "object_type": "outcome",
                    "effect_size": effect,
                    "avg_confidence": round(self._avg_confidence([i, o] + (effs[:1] if effect else [])), 6),
                }
                triplet.update(other_entities)
                yield triplet

        # I -> P (applies_to)
        for i in ints:
            for p in pops:
                triplet_count += 1
                triplet = {
                    "subject_text": i["word"],
                    "subject_type": "intervention",
                    "relation": "applies_to",
                    "object_text": p["word"],
                    "object_type": "population",
                    "effect_size": None,
                    "avg_confidence": round(self._avg_confidence([i, p]), 6),
                }
                triplet.update(other_entities)
                yield triplet

        # (Optional) O -> P (experienced_by)
        if self.attach_outcome_population:
            for o in outs:
                for p in pops:
                    triplet_count += 1
                    triplet = {
                        "subject_text": o["word"],
                        "subject_type": "outcome",
                        "relation": "experienced_by",
                        "object_text": p["word"],
                        "object_type": "population",
                        "effect_size": None,
                        "avg_confidence": round(self._avg_confidence([o, p]), 6),
                    }
                    triplet.update(other_entities)
                    yield triplet
        
        self.logger.debug(f"Generated {triplet_count} triplets from row")

    #
    # Pipeline
    #
    def extract(self) -> None:
        """
        Read input CSV rows, generate triplets, deduplicate, and write output CSV.
        """
        self.logger.info(f"Starting extraction from {self.input_csv} to {self.output_csv}")
        self.logger.info(f"Config - min_score: {self.min_score}, attach_outcome_population: {self.attach_outcome_population}")
        
        input_fields_hint = {
            'file', 'page', 'title', 'author', 'modDate', 'creationDate', 'subject', 'textBlock', 'entities'
        }
        
        # Base output fields
        base_out_fields = [
            "file", "page", "title",
            "subject_text", "subject_type",
            "relation",
            "object_text", "object_type",
            "effect_size",
            "avg_confidence",
            "textBlock",
        ]

        dedup_key_set = set()
        to_write: List[Dict[str, Any]] = []
        total_rows = 0
        total_triplets = 0

        # First pass: collect all data and discover entity types
        self.logger.info("First pass: discovering all entity types...")
        with open(self.input_csv, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            missing = input_fields_hint - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Missing expected input columns: {sorted(missing)}")
            
            self.logger.info(f"Input CSV has columns: {reader.fieldnames}")

            for row_idx, row in enumerate(reader, 1):
                total_rows += 1
                if row_idx % 100 == 0:
                    self.logger.info(f"Processed {row_idx} rows, generated {total_triplets} triplets so far")
                
                base = {
                    "file": row.get("file", ""),
                    "page": row.get("page", ""),
                    "title": row.get("title", ""),
                    "textBlock": self._normalize_text(row.get("textBlock", "")),
                }
                
                row_triplets = 0
                for t in self._triplets_from_row(row):
                    key = (
                        base["file"],
                        base["page"],
                        base["title"],
                        t["subject_text"].lower(),
                        t["subject_type"],
                        t["relation"],
                        t["object_text"].lower(),
                        t["object_type"],
                        (t["effect_size"] or "").lower(),
                    )
                    if key in dedup_key_set:
                        self.logger.debug(f"Skipping duplicate triplet: {t['subject_text']} -> {t['object_text']}")
                        continue
                    dedup_key_set.add(key)
                    row_triplets += 1
                    total_triplets += 1

                    to_write.append({
                        **base,
                        **t
                    })
                
                if row_triplets == 0:
                    self.logger.debug(f"No triplets generated for row {row_idx}")

        # Log discovered entity types
        other_entity_types = sorted(self.all_entity_types - self.PICO_GROUPS)
        self.logger.info(f"Discovered entity types - PICO: {sorted(self.PICO_GROUPS)}")
        self.logger.info(f"Discovered entity types - Other: {other_entity_types}")
        
        # Create final output fields including other entity columns
        out_fields = base_out_fields + other_entity_types

        self.logger.info(f"Extraction complete - processed {total_rows} rows, generated {total_triplets} unique triplets")

        with open(self.output_csv, 'w', newline='', encoding='utf-8') as out:
            writer = csv.DictWriter(out, fieldnames=out_fields)
            writer.writeheader()
            for rec in to_write:
                # Ensure all fields are present (fill missing other entity columns with empty strings)
                for field in out_fields:
                    if field not in rec:
                        rec[field] = ""
                writer.writerow(rec)
        
        self.logger.info(f"Written {len(to_write)} triplets to {self.output_csv}")
        self.logger.info(f"Output CSV columns: {out_fields}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
        Build PICO-style triplets from a CSV that includes an 'entities' JSON column.
        Example usage:
          python triplets.py --input_csv econ.csv --output_csv triplets.csv --min_score 0.6
    """.strip())
    parser.add_argument("--input_csv", type=str, required=True, help="Input CSV path with entity detections.")
    parser.add_argument("--output_csv", type=str, default="triplets.csv", help="Output CSV path for triplets.")
    parser.add_argument("--min_score", type=float, default=0.0, help="Minimum entity confidence to keep.")
    parser.add_argument("--attach_outcome_population", action="store_true",
                        help="Also create (outcome)-[experienced_by]->(population) edges.")
    parser.add_argument("--keep_first_effect_only", action="store_true",
                        help="If multiple effect_size mentions exist, keep only the first (default behaviour).")
    parser.add_argument("--log_level", type=str, default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Set logging level (default: INFO)")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    extractor = CSVTripletExtractor(
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        min_score=args.min_score,
        attach_outcome_population=args.attach_outcome_population,
        keep_first_effect_only=args.keep_first_effect_only or True,
    )
    extractor.extract()
    print(f"Done. Triplets written to {args.output_csv}")