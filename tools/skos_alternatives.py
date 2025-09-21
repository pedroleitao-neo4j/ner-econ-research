import argparse
import pandas as pd
import rdflib
from rdflib import Graph, Namespace
from typing import Dict, List, Set
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

def load_skos_mappings(skos_url: str) -> Dict[str, str]:
    """
    Load SKOS RDF from a URL and create bidirectional mapping between preferred and alternative labels.
    The URL can point to a plain RDF file, a .gz file, or a .zip containing an RDF file.
    
    Args:
        skos_url: URL to SKOS RDF (plain, .gz, or .zip)
        
    Returns:
        Dictionary mapping terms (case-insensitive) to their alternative terms (English)
    """
    g = Graph()

    # If compressed, download and parse from bytes; otherwise let rdflib fetch the URL directly.
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

    mappings = {}
    
    # Query for concepts with English preferred labels and English alternative labels
    query = """
    SELECT ?concept ?prefLabel ?altLabel WHERE {
        ?concept a skos:Concept ;
                 skos:prefLabel ?prefLabel .
        FILTER(lang(?prefLabel) = "en" || lang(?prefLabel) = "")
        OPTIONAL { 
            ?concept skos:altLabel ?altLabel .
            FILTER(lang(?altLabel) = "en" || lang(?altLabel) = "")
        }
    }
    """
    
    for row in g.query(query, initNs={'skos': SKOS}):
        concept, pref_label, alt_label = row
        pref_str = str(pref_label).strip()
        
        # Create bidirectional mappings between preferred and alternative labels
        if alt_label:
            alt_str = str(alt_label).strip()
            # Map preferred label to alternative label
            mappings[_norm(pref_str)] = alt_str
            # Map alternative label to preferred label
            mappings[_norm(alt_str)] = pref_str
    
    return mappings

def find_alternative_terms(df: pd.DataFrame, columns: List[str], mappings: Dict[str, str], suffix: str = "alternative") -> pd.DataFrame:
    """
    Add alternative term columns based on SKOS mappings.
    
    Args:
        df: Input DataFrame
        columns: List of column names to find alternatives for
        mappings: Dictionary mapping terms to their alternatives
        suffix: Suffix for the new column names
        
    Returns:
        DataFrame with additional alternative term columns
    """
    df_copy = df.copy()
    
    for col in columns:
        if col not in df_copy.columns:
            logger.warning(f"Column '{col}' not found in CSV file")
            continue
            
        alternative_col = f"{col}_{suffix}"
        alternative_values = []
        
        for value in df_copy[col]:
            if pd.isna(value):
                alternative_values.append(value)
            else:
                value_str = str(value).strip()
                
                # Check if value contains semicolon separator
                if ";" in value_str:
                    # Split on ';' regardless of spacing and preserve positions
                    elements = [elem.strip() for elem in value_str.split(";")]
                    alternative_elements = []
                    matched_any = False
                    for elem in elements:
                        norm = _norm(elem)
                        if norm in mappings:
                            alternative_elements.append(mappings[norm])
                            matched_any = True
                        else:
                            # Leave unmatched elements blank to preserve positions
                            alternative_elements.append("")
                            logger.debug(f"No alternative found for element '{elem}' in column '{col}'")
                    if matched_any:
                        alternative = "; ".join(alternative_elements)
                        alternative_values.append(alternative)
                        logger.debug(f"Found alternative for '{value_str}': '{alternative}' in column '{col}'")
                    else:
                        # No alternatives found; leave empty (not NA)
                        alternative_values.append("")
                else:
                    # Single value, only populate if an alternative exists
                    norm = _norm(value_str)
                    if norm in mappings:
                        alternative_values.append(mappings[norm])
                    else:
                        # Leave empty (not NA)
                        alternative_values.append("")
        
        df_copy[alternative_col] = alternative_values
    
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
        # Load SKOS mappings
        logger.info("Loading SKOS mappings... this may take a while for large files.")
        mappings = load_skos_mappings(args.skos)
        logger.info(f"Loaded {len(mappings)} term mappings")
        
        # Load CSV file
        logger.info("Loading CSV file...")
        df = pd.read_csv(args.input_csv)
        logger.info(f"Loaded CSV with {len(df)} rows and {len(df.columns)} columns")
        
        # Find alternative terms for specified columns
        logger.info(f"Finding alternatives for columns: {', '.join(columns)}")
        df_with_alternatives = find_alternative_terms(df, columns, mappings, args.suffix)
        
        # Save output
        output_file = args.output_csv
        df_with_alternatives.to_csv(output_file, index=False)
        logger.info(f"Saved data with alternative terms to {output_file}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
