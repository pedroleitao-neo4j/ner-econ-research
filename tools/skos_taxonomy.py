import argparse
import pandas as pd
import rdflib
from rdflib import Graph, Namespace
from typing import Dict, List, Set, Tuple, Iterable
import sys
import logging
import urllib.request
import urllib.parse
import io
import gzip
import zipfile
from rdflib.util import guess_format

# Define SKOS namespace
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _norm(text: str) -> str:
    """
    Normalize text for case-insensitive matching.
    Uses Unicode-aware casefolding and strips surrounding whitespace.
    """
    return text.strip().casefold()

def _download_and_extract(url: str) -> tuple[bytes, str]:
    """
    Download a URL and, if it's a .gz or .zip, return the decompressed RDF bytes and an inner filename
    used to guess format. Otherwise return the raw bytes and the URL's basename.
    """
    with urllib.request.urlopen(url) as resp:
        content = resp.read()
    lower = url.lower()
    basename = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]

    if lower.endswith(".gz"):
        data = gzip.decompress(content)
        inner_name = basename[:-3] if basename.endswith(".gz") else basename
        logger.info(f"Decompressed gzip from URL, inner name: {inner_name}")
        return data, inner_name

    if lower.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            preferred_ext = (".ttl", ".rdf", ".owl", ".nt", ".n3", ".xml", ".trig", ".nq")
            inner_name = None
            # pick the first file matching preferred extensions
            for ext in preferred_ext:
                for zi in zf.infolist():
                    if not zi.is_dir() and zi.filename.lower().endswith(ext):
                        inner_name = zi.filename
                        break
                if inner_name:
                    break
            # fallback: first non-directory entry
            if not inner_name:
                for zi in zf.infolist():
                    if not zi.is_dir():
                        inner_name = zi.filename
                        break
            if not inner_name:
                raise ValueError("ZIP archive contains no files")
            logger.info(f"Selected '{inner_name}' from ZIP archive")
            data = zf.read(inner_name)
            return data, inner_name

    # not compressed
    return content, basename

def _parse_skos_graph(skos_url: str) -> Graph:
    """
    Parse SKOS RDF from a URL (supports plain, .gz, .zip) and return an rdflib Graph.
    """
    g = Graph()

    if skos_url.lower().endswith((".gz", ".zip")):
        data, inner_name = _download_and_extract(skos_url)
        fmt = guess_format(inner_name or skos_url) or "xml"
        try:
            g.parse(source=io.BytesIO(data), format=fmt)
        except Exception as e:
            logger.warning(f"Parsing with format '{fmt}' failed ({e}); trying fallbacks...")
            for alt in ("turtle", "xml", "nt", "n3"):
                if alt == fmt:
                    continue
                try:
                    g.parse(source=io.BytesIO(data), format=alt)
                    logger.info(f"Parsed RDF using fallback format '{alt}'")
                    break
                except Exception:
                    continue
            else:
                raise
    else:
        g.parse(skos_url)

    return g

def load_skos_index(skos_url: str) -> Tuple[Dict[str, str], Dict[str, Set[rdflib.term.Node]], Dict[rdflib.term.Node, str], Dict[rdflib.term.Node, List[rdflib.term.Node]]]:
    """
    Load SKOS and build:
    - mappings: bidirectional pref<->alt label mapping (normalized key)
    - label_to_concepts: normalized label -> set of concept nodes
    - concept_pref_label: concept node -> preferred label string
    - broader_of: concept node -> list of broader (parent) concept nodes
    Only English or language-neutral labels are considered.
    """
    g = _parse_skos_graph(skos_url)

    mappings: Dict[str, str] = {}
    label_to_concepts: Dict[str, Set[rdflib.term.Node]] = {}
    concept_pref_label: Dict[rdflib.term.Node, str] = {}
    broader_of: Dict[rdflib.term.Node, List[rdflib.term.Node]] = {}

    # Collect preferred labels
    for concept, _, pref_label in g.triples((None, SKOS.prefLabel, None)):
        # Filter by lang 'en' or no lang
        if getattr(pref_label, 'language', None) in ("en", None, ""):
            pref_str = str(pref_label).strip()
            concept_pref_label[concept] = pref_str
            label_to_concepts.setdefault(_norm(pref_str), set()).add(concept)

    # Collect alternative labels and build bidirectional mappings
    for concept, _, alt_label in g.triples((None, SKOS.altLabel, None)):
        if getattr(alt_label, 'language', None) in ("en", None, ""):
            alt_str = str(alt_label).strip()
            # Add label->concept mapping
            label_to_concepts.setdefault(_norm(alt_str), set()).add(concept)
            # Map alt -> pref (if pref known)
            pref_str = concept_pref_label.get(concept)
            if pref_str:
                mappings[_norm(alt_str)] = pref_str
                # Map pref -> alt (note: if multiple alts exist, last one wins)
                mappings[_norm(pref_str)] = alt_str

    # Ensure pref->alt mapping exists even if no alt labels were seen (not needed for taxonomy, but preserves behavior)
    # We won't map pref->pref; only keep existing pref->alt when available.

    # Collect broader relations
    for child, _, parent in g.triples((None, SKOS.broader, None)):
        broader_of.setdefault(child, []).append(parent)

    return mappings, label_to_concepts, concept_pref_label, broader_of

def load_skos_mappings(skos_url: str) -> Dict[str, str]:
    """
    Backwards-compatible API: return only mappings, built from the SKOS index.
    """
    mappings, _, _, _ = load_skos_index(skos_url)
    return mappings

def _label_for_concept(concept: rdflib.term.Node, concept_pref_label: Dict[rdflib.term.Node, str]) -> str:
    label = concept_pref_label.get(concept)
    if label:
        return label
    # fallback: compact URI fragment or full URI
    s = str(concept)
    if "#" in s:
        return s.rsplit('#', 1)[-1]
    return s.rsplit('/', 1)[-1] if '/' in s else s

def build_taxonomy_path_for_label(label: str,
                                  label_to_concepts: Dict[str, Set[rdflib.term.Node]],
                                  concept_pref_label: Dict[rdflib.term.Node, str],
                                  broader_of: Dict[rdflib.term.Node, List[rdflib.term.Node]],
                                  level_separator: str = "->",
                                  max_depth: int = 50) -> str:
    """
    Given a label string, find a matching concept and traverse skos:broader upwards,
    returning a string like 'level1 > level2 > ... > root'.
    """
    norm = _norm(label)
    concepts = list(label_to_concepts.get(norm, []))
    if not concepts:
        return ""
    # Deterministic choice if ambiguous
    concepts.sort(key=lambda c: _label_for_concept(c, concept_pref_label))
    node = concepts[0]

    path: List[str] = []
    seen: Set[rdflib.term.Node] = set()
    depth = 0
    while node is not None and node not in seen and depth < max_depth:
        seen.add(node)
        path.append(_label_for_concept(node, concept_pref_label))
        parents = broader_of.get(node, [])
        if not parents:
            break
        # Choose deterministically by label
        parents_sorted = sorted(parents, key=lambda c: _label_for_concept(c, concept_pref_label))
        node = parents_sorted[0]
        depth += 1

    return level_separator.join(path)

def find_alternative_terms(df: pd.DataFrame,
                           columns: List[str],
                           mappings: Dict[str, str],
                           suffix: str = "alternative",
                           taxonomy_index: Tuple[
                               Dict[str, Set[rdflib.term.Node]],
                               Dict[rdflib.term.Node, str],
                               Dict[rdflib.term.Node, List[rdflib.term.Node]]
                           ] | None = None) -> pd.DataFrame:
    """
    Add alternative term columns based on SKOS mappings.
    Additionally, when an alternative is found, add a taxonomy path column
    named '{col}_{suffix}_taxonomy' with the upward SKOS hierarchy for that entry.
    
    Args:
        df: Input DataFrame
        columns: List of column names to find alternatives for
        mappings: Dictionary mapping terms to their alternatives
        suffix: Suffix for the new column names
        
    Returns:
        DataFrame with additional alternative and taxonomy columns
    """
    df_copy = df.copy()
    label_to_concepts: Dict[str, Set[rdflib.term.Node]] | None = None
    concept_pref_label: Dict[rdflib.term.Node, str] | None = None
    broader_of: Dict[rdflib.term.Node, List[rdflib.term.Node]] | None = None

    if taxonomy_index is not None:
        label_to_concepts, concept_pref_label, broader_of = taxonomy_index
    
    for col in columns:
        if col not in df_copy.columns:
            logger.warning(f"Column '{col}' not found in CSV file")
            continue
            
        alternative_col = f"{col}_{suffix}"
        alternative_values: List[str] = []
        taxonomy_values: List[str] = []
        
        for value in df_copy[col]:
            if pd.isna(value):
                alternative_values.append(value)
                taxonomy_values.append(value)
            else:
                value_str = str(value).strip()
                
                # Check if value contains semicolon separator
                if ";" in value_str:
                    # Split on ';' regardless of spacing and preserve positions
                    elements = [elem.strip() for elem in value_str.split(";")]
                    alternative_elements = []
                    taxonomy_elements = []
                    matched_any = False
                    for elem in elements:
                        norm = _norm(elem)
                        if norm in mappings:
                            alternative_elements.append(mappings[norm])
                            matched_any = True
                            if taxonomy_index is not None and label_to_concepts is not None and concept_pref_label is not None and broader_of is not None:
                                taxonomy_elements.append(
                                    build_taxonomy_path_for_label(elem, label_to_concepts, concept_pref_label, broader_of)
                                )
                            else:
                                taxonomy_elements.append("")
                        else:
                            # Leave unmatched elements blank to preserve positions
                            alternative_elements.append("")
                            taxonomy_elements.append("")
                            logger.debug(f"No alternative found for element '{elem}' in column '{col}'")
                    if matched_any:
                        alternative = "; ".join(alternative_elements)
                        alternative_values.append(alternative)
                        logger.debug(f"Found alternative for '{value_str}': '{alternative}' in column '{col}'")
                        taxonomy_values.append("; ".join(taxonomy_elements))
                    else:
                        # No alternatives found; leave empty (not NA)
                        alternative_values.append("")
                        taxonomy_values.append("")
                else:
                    # Single value, only populate if an alternative exists
                    norm = _norm(value_str)
                    if norm in mappings:
                        alternative_values.append(mappings[norm])
                        if taxonomy_index is not None and label_to_concepts is not None and concept_pref_label is not None and broader_of is not None:
                            taxonomy_values.append(
                                build_taxonomy_path_for_label(value_str, label_to_concepts, concept_pref_label, broader_of)
                            )
                        else:
                            taxonomy_values.append("")
                    else:
                        # Leave empty (not NA)
                        alternative_values.append("")
                        taxonomy_values.append("")
        
        df_copy[alternative_col] = alternative_values
        taxonomy_col = f"{col}_{suffix}_taxonomy"
        df_copy[taxonomy_col] = taxonomy_values
    
    return df_copy

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find alternative terms for CSV column values using SKOS preferred/alternative labels"
    )
    parser.add_argument("--input_csv", required=True, help="Path to input CSV file")
    parser.add_argument("--columns", nargs='+', required=True, help="List of columns to find alternatives for")
    parser.add_argument("--skos", required=True, help="URL to SKOS RDF (plain, .gz, or .zip)")
    parser.add_argument("--output_csv", required=True, help="Output CSV file")
    parser.add_argument("--suffix", default="alternative", help="Suffix for alternative column names (default: 'alternative')")
    parser.add_argument("--log_level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    
    logging.getLogger().setLevel(getattr(logging, parser.parse_args().log_level.upper(), logging.INFO))
    
    args = parser.parse_args()
    
    # Parse column list
    columns = args.columns
    
    try:
        # Load SKOS mappings and taxonomy index
        logger.info("Loading SKOS taxonomy... this may take a while for large files.")
        mappings, label_to_concepts, concept_pref_label, broader_of = load_skos_index(args.skos)
        logger.info(f"Loaded {len(mappings)} label mappings; indexed {len(concept_pref_label)} concepts")
        
        # Load CSV file
        logger.info("Loading CSV file...")
        df = pd.read_csv(args.input_csv)
        logger.info(f"Loaded CSV with {len(df)} rows and {len(df.columns)} columns")
        
        # Find alternative terms and taxonomy for specified columns
        logger.info(f"Finding alternatives and taxonomy for columns: {', '.join(columns)}")
        df_with_alternatives = find_alternative_terms(
            df, columns, mappings, args.suffix,
            taxonomy_index=(label_to_concepts, concept_pref_label, broader_of)
        )
        
        # Save output
        output_file = args.output_csv
        df_with_alternatives.to_csv(output_file, index=False)
        logger.info(f"Saved data with alternative terms to {output_file}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
