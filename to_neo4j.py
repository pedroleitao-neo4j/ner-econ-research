import os
import argparse

class CypherFromTripletsWithFTS:
    """
    Generate a Cypher script from a triplets CSV that:
      - Creates uniqueness constraints
      - Creates full-text indexes (Intervention, Outcome, Population, Coreference, Excerpt, Document) for Neo4j 5
      - Loads CSV and builds the graph (no APOC required)

    Expected CSV columns:
      file,title,subject_text,subject_type,relation,object_text,object_type,effect_size,avg_confidence,textBlock,page,
      per,org,loc,affiliation,author
    """

    def __init__(self, args):
        self.args = args

    def _script(self) -> str:
        # Note: Double braces {{ }} are used to emit single { } into the Cypher output from an f-string.

        alt_cols_cypher = []
        if self.args.add_alternative_columns:
            for col in self.args.add_alternative_columns:
                alt_cols_cypher.append(f"  trim(coalesce(row.{col}{self.args.alternative_suffix},'')) AS {col}_alt_text,")

        alt_lists_cypher = []
        if self.args.add_alternative_columns:
            for col in self.args.add_alternative_columns:
                alt_lists_cypher.append(f"  CASE WHEN {col}_alt_text = '' THEN [] ELSE [t IN split({col}_alt_text, ';') | trim(t)] END AS {col}_alt_list,")

        per_alt_cypher = ""
        if self.args.add_alternative_columns and 'per' in self.args.add_alternative_columns:
            per_alt_cypher = f"""
  FOREACH (alt_per IN CASE WHEN size(per_alt_list) > i AND per_alt_list[i] <> '' THEN [per_alt_list[i]] ELSE [] END |
    MERGE (alt_pr:Person {{unique_key: 'person|' + toLower(alt_per)}})
      ON CREATE SET alt_pr.file = file, alt_pr.title = alt_per, alt_pr.text = alt_per, alt_pr.type = 'person', alt_pr.page = page_int
    MERGE (pr)-[:{self.args.alternative_relationship_type}]->(alt_pr)
  )"""

        org_alt_cypher = ""
        if self.args.add_alternative_columns and 'org' in self.args.add_alternative_columns:
            org_alt_cypher = f"""
  FOREACH (alt_org IN CASE WHEN size(org_alt_list) > i AND org_alt_list[i] <> '' THEN [org_alt_list[i]] ELSE [] END |
    MERGE (alt_g:Organization {{unique_key: 'organization|' + toLower(alt_org)}})
      ON CREATE SET alt_g.file = file, alt_g.title = alt_org, alt_g.text = alt_org, alt_g.type = 'organization', alt_g.page = page_int
    MERGE (g)-[:{self.args.alternative_relationship_type}]->(alt_g)
  )"""

        loc_alt_cypher = ""
        if self.args.add_alternative_columns and 'loc' in self.args.add_alternative_columns:
            loc_alt_cypher = f"""
  FOREACH (alt_loc IN CASE WHEN size(loc_alt_list) > i AND loc_alt_list[i] <> '' THEN [loc_alt_list[i]] ELSE [] END |
    MERGE (alt_l:Location {{unique_key: 'location|' + toLower(alt_loc)}})
      ON CREATE SET alt_l.file = file, alt_l.title = alt_loc, alt_l.text = alt_loc, alt_l.type = 'location', alt_l.page = page_int
    MERGE (l)-[:{self.args.alternative_relationship_type}]->(alt_l)
  )"""

        return f"""// Auto-generated Cypher import script with Full-Text Indexes (Neo4j 5)
// Place {self.args.csv_basename} into Neo4j's import/ directory.

/// ---- Constraints ----
CREATE CONSTRAINT IF NOT EXISTS FOR (i:Intervention) REQUIRE i.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (o:Outcome)      REQUIRE o.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:Population)   REQUIRE p.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Coreference)  REQUIRE c.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document)     REQUIRE d.doc_key    IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Excerpt)      REQUIRE e.excerpt_key IS UNIQUE;
// New entity constraints
CREATE CONSTRAINT IF NOT EXISTS FOR (pr:Person)        REQUIRE pr.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (g:Organization)   REQUIRE g.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location)       REQUIRE l.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (af:Affiliation)   REQUIRE af.unique_key IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (au:Author)        REQUIRE au.unique_key IS UNIQUE;

/// ---- Full-text indexes (Neo4j 5 syntax) ----
CREATE FULLTEXT INDEX intervention_text_fts IF NOT EXISTS
FOR (i:Intervention) ON EACH [i.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX outcome_text_fts IF NOT EXISTS
FOR (o:Outcome) ON EACH [o.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX population_text_fts IF NOT EXISTS
FOR (p:Population) ON EACH [p.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX coreference_text_fts IF NOT EXISTS
FOR (c:Coreference) ON EACH [c.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX excerpt_text_fts IF NOT EXISTS
FOR (e:Excerpt) ON EACH [e.text, e.title]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX document_title_fts IF NOT EXISTS
FOR (d:Document) ON EACH [d.title]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

// New entity FTS indexes
CREATE FULLTEXT INDEX person_text_fts IF NOT EXISTS
FOR (pr:Person) ON EACH [pr.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX organization_text_fts IF NOT EXISTS
FOR (g:Organization) ON EACH [g.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX location_text_fts IF NOT EXISTS
FOR (l:Location) ON EACH [l.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX affiliation_text_fts IF NOT EXISTS
FOR (af:Affiliation) ON EACH [af.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

CREATE FULLTEXT INDEX author_text_fts IF NOT EXISTS
FOR (au:Author) ON EACH [au.text]
OPTIONS {{ indexConfig: {{ `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true }} }};

/// ---- Param for the CSV file name ----
:param csvFile => '{self.args.csv_basename}';

/// ---- Import pipeline ----
LOAD CSV WITH HEADERS FROM 'file:///' + $csvFile AS row
WITH row
WHERE trim(coalesce(row.subject_text,'')) <> '' AND trim(coalesce(row.object_text,'')) <> ''

WITH
  row,
  toLower(trim(row.subject_type)) AS s_type,
  toLower(trim(row.object_type))  AS o_type,
  toLower(trim(row.relation))     AS rel_lc,
  trim(row.subject_text)          AS s_text,
  trim(row.object_text)           AS o_text,
  trim(coalesce(row.file,''))     AS file,
  trim(coalesce(row.title,''))    AS title,
  trim(coalesce(row.textBlock,'')) AS textBlock,
  trim(coalesce(row.effect_size,'')) AS effect_size,
  trim(row.page) AS page,
  toFloat(coalesce(row.avg_confidence,'0')) AS avg_confidence,
  // New optional entity fields
  trim(coalesce(row.per,''))          AS per_text,
  trim(coalesce(row.org,''))          AS org_text,
  trim(coalesce(row.loc,''))          AS loc_text,
  trim(coalesce(row.affiliation,''))  AS affiliation_text,
  trim(coalesce(row.author,''))       AS author_text
  {',' if self.args.add_alternative_columns else ''}{''.join(alt_cols_cypher).rstrip(',')}

WITH
  row, s_type, o_type, rel_lc, s_text, o_text, file, title, textBlock, effect_size, page, avg_confidence,
  per_text, org_text, loc_text, affiliation_text, author_text,
  { ''.join([f"{col}_alt_text, " for col in self.args.add_alternative_columns or []]) }
  CASE
    WHEN page = '' THEN NULL
    ELSE toInteger(page)
  END AS page_int,
  (s_type + '|' + toLower(s_text)) AS s_key,
  (o_type + '|' + toLower(o_text)) AS o_key,
  (file + '|' + title) AS doc_key,
  (file + '|' + title + '|' + left(textBlock, 1024)) AS excerpt_key,
  // New entity lists (split on ';' and trim; ignore empty parts)
  CASE WHEN per_text = '' THEN [] ELSE [t IN split(per_text, ';') WHERE trim(t) <> '' | trim(t)] END AS per_list,
  CASE WHEN org_text = '' THEN [] ELSE [t IN split(org_text, ';') WHERE trim(t) <> '' | trim(t)] END AS org_list,
  CASE WHEN loc_text = '' THEN [] ELSE [t IN split(loc_text, ';') WHERE trim(t) <> '' | trim(t)] END AS loc_list,
  {''.join(alt_lists_cypher)}
  // Keep single-value keys for others
  CASE WHEN affiliation_text <> '' THEN 'affiliation|'  + toLower(affiliation_text) ELSE NULL END AS affiliation_key,
  CASE WHEN author_text      <> '' THEN 'author|'       + toLower(author_text)      ELSE NULL END AS author_key

// Document & Excerpt (provenance)
MERGE (d:Document {{doc_key: doc_key}})
  ON CREATE SET d.file = file, d.title = title

MERGE (x:Excerpt {{excerpt_key: excerpt_key}})
  ON CREATE SET
    x.file  = file,
    x.title = CASE
                WHEN textBlock IS NULL THEN ''
                WHEN size(textBlock) > 120 THEN substring(textBlock, 0, 120) + '...'
                ELSE textBlock
              END,
    x.text  = textBlock,
    x.page = page_int

MERGE (d)-[:HAS_EXCERPT]->(x)

FOREACH (_ IN CASE WHEN affiliation_text <> '' THEN [1] ELSE [] END |
  MERGE (af:Affiliation {{unique_key: affiliation_key}})
    ON CREATE SET
      af.file = file,
      af.title = affiliation_text,
      af.text = affiliation_text,
      af.type = 'affiliation',
      af.page = page_int
  MERGE (af)-[maf:MENTIONED_IN]->(x)
    ON CREATE SET maf.file = file, maf.title = title, maf.page = page_int
)

FOREACH (_ IN CASE WHEN author_text <> '' THEN [1] ELSE [] END |
  MERGE (au:Author {{unique_key: author_key}})
    ON CREATE SET
      au.file = file,
      au.title = author_text,
      au.text = author_text,
      au.type = 'author',
      au.page = page_int
  MERGE (au)-[mau:MENTIONED_IN]->(x)
    ON CREATE SET mau.file = file, mau.title = title, mau.page = page_int
)

// Persons, Organizations, Locations extracted from lists
FOREACH (i IN CASE WHEN size(per_list) > 0 THEN range(0, size(per_list)-1) ELSE [] END |
  MERGE (pr:Person {{unique_key: 'person|' + toLower(per_list[i])}})
    ON CREATE SET pr.file = file, pr.title = per_list[i], pr.text = per_list[i], pr.type = 'person', pr.page = page_int
  MERGE (pr)-[mpr:MENTIONED_IN]->(x)
    ON CREATE SET mpr.file = file, mpr.title = title, mpr.page = page_int
  {per_alt_cypher}
)

FOREACH (i IN CASE WHEN size(org_list) > 0 THEN range(0, size(org_list)-1) ELSE [] END |
  MERGE (g:Organization {{unique_key: 'organization|' + toLower(org_list[i])}})
    ON CREATE SET g.file = file, g.title = org_list[i], g.text = org_list[i], g.type = 'organization', g.page = page_int
  MERGE (g)-[mg:MENTIONED_IN]->(x)
    ON CREATE SET mg.file = file, mg.title = title, mg.page = page_int
  {org_alt_cypher}
)

FOREACH (i IN CASE WHEN size(loc_list) > 0 THEN range(0, size(loc_list)-1) ELSE [] END |
  MERGE (l:Location {{unique_key: 'location|' + toLower(loc_list[i])}})
    ON CREATE SET l.file = file, l.title = loc_list[i], l.text = loc_list[i], l.type = 'location', l.page = page_int
  MERGE (l)-[ml:MENTIONED_IN]->(x)
    ON CREATE SET ml.file = file, ml.title = title, ml.page = page_int
  {loc_alt_cypher}
)

// Subject Node (direct type creation)
FOREACH (_ IN CASE WHEN s_type = 'intervention' THEN [1] ELSE [] END |
  MERGE (s:Intervention {{unique_key: s_key}})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)
FOREACH (_ IN CASE WHEN s_type = 'outcome' THEN [1] ELSE [] END |
  MERGE (s:Outcome {{unique_key: s_key}})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)
FOREACH (_ IN CASE WHEN s_type = 'population' THEN [1] ELSE [] END |
  MERGE (s:Population {{unique_key: s_key}})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)
FOREACH (_ IN CASE WHEN s_type = 'coreference' THEN [1] ELSE [] END |
  MERGE (s:Coreference {{unique_key: s_key}})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)

// Object Node (direct type creation)
FOREACH (_ IN CASE WHEN o_type = 'intervention' THEN [1] ELSE [] END |
  MERGE (o:Intervention {{unique_key: o_key}})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)
FOREACH (_ IN CASE WHEN o_type = 'outcome' THEN [1] ELSE [] END |
  MERGE (o:Outcome {{unique_key: o_key}})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)
FOREACH (_ IN CASE WHEN o_type = 'population' THEN [1] ELSE [] END |
  MERGE (o:Population {{unique_key: o_key}})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)
FOREACH (_ IN CASE WHEN o_type = 'coreference' THEN [1] ELSE [] END |
  MERGE (o:Coreference {{unique_key: o_key}})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)

// Get references to subject and object nodes for relationships
WITH row, s_type, o_type, rel_lc, s_key, o_key, file, title, textBlock, effect_size, page, page_int, avg_confidence, d, x
OPTIONAL MATCH (s) WHERE s.unique_key = s_key
OPTIONAL MATCH (o) WHERE o.unique_key = o_key

// Provenance mentions
MERGE (s)-[ms:MENTIONED_IN]->(x)
  ON CREATE SET
    ms.file = file,
    ms.title = title,
    ms.page = page_int
MERGE (o)-[mo:MENTIONED_IN]->(x)
  ON CREATE SET
    mo.file = file,
    mo.title = title,
    mo.page = page_int

// Relationships without APOC (FOREACH/CASE to choose rel type)
FOREACH (_ IN CASE WHEN rel_lc = 'impacts' THEN [1] ELSE [] END |
  MERGE (s)-[r:IMPACTS]->(o)
    ON CREATE SET
      r.effect_size = CASE WHEN effect_size = '' THEN NULL ELSE effect_size END,
      r.avg_confidence = avg_confidence,
      r.file = file,
      r.title = title,
      r.page = page_int
)
FOREACH (_ IN CASE WHEN rel_lc = 'applies_to' THEN [1] ELSE [] END |
  MERGE (s)-[r:APPLIES_TO]->(o)
    ON CREATE SET
      r.effect_size = CASE WHEN effect_size = '' THEN NULL ELSE effect_size END,
      r.avg_confidence = avg_confidence, r.file = file, r.title = title,
      r.page = page_int
)
FOREACH (_ IN CASE WHEN rel_lc = 'experienced_by' THEN [1] ELSE [] END |
  MERGE (s)-[r:EXPERIENCED_BY]->(o)
    ON CREATE SET
      r.effect_size = CASE WHEN effect_size = '' THEN NULL ELSE effect_size END,
      r.avg_confidence = avg_confidence, r.file = file, r.title = title,
      r.page = page_int
);
"""

    def generate(self) -> None:
        self.args.csv_basename = os.path.basename(self.args.input_csv)
        with open(self.args.output_cypher, "w", encoding="utf-8") as f:
            f.write(self._script())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
        Generate a Cypher import script (with Neo4j 5 full-text indexes) from a triplets CSV.
        Usage:
          python cypher_from_triplets_fts.py --input_csv triplets.csv --output_cypher import_triplets.cypher
    """.strip())
    parser.add_argument("--input_csv", type=str, required=True, help="Path to the triplets CSV.")
    parser.add_argument("--output_cypher", type=str, default="import_triplets.cypher", help="Output Cypher script path.")
    parser.add_argument("--alternative_suffix", type=str, required=False, default="_alternative", help="Suffix for alternative column names (default: '_alternative').")
    parser.add_argument("--add_alternative_columns", type=str, required=False, nargs='+', help="List of columns to add alternatives columns for (optional).")
    parser.add_argument("--alternative_relationship_type", type=str, required=False, default="HAS_ALTERNATIVE", help="Relationship type for alternatives (default: 'HAS_ALTERNATIVE').")
    args = parser.parse_args()

    gen = CypherFromTripletsWithFTS(args)
    gen.generate()
    print(f"Wrote {args.output_cypher}. Copy {os.path.basename(args.input_csv)} to Neo4j import/ and run the script.")
