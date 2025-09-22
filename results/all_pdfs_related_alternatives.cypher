// Auto-generated Cypher import script with Full-Text Indexes (Neo4j 5)
// Place all_pdfs_related_alternatives.csv into Neo4j's import/ directory.

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
// Taxonomy constraints
CREATE CONSTRAINT IF NOT EXISTS FOR (t:Taxon)          REQUIRE t.unique_key IS UNIQUE;

/// ---- Full-text indexes (Neo4j 5 syntax) ----
CREATE FULLTEXT INDEX intervention_text_fts IF NOT EXISTS
FOR (i:Intervention) ON EACH [i.text]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

CREATE FULLTEXT INDEX outcome_text_fts IF NOT EXISTS
FOR (o:Outcome) ON EACH [o.text]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

CREATE FULLTEXT INDEX population_text_fts IF NOT EXISTS
FOR (p:Population) ON EACH [p.text]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

CREATE FULLTEXT INDEX coreference_text_fts IF NOT EXISTS
FOR (c:Coreference) ON EACH [c.text]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

CREATE FULLTEXT INDEX excerpt_text_fts IF NOT EXISTS
FOR (e:Excerpt) ON EACH [e.text, e.title]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

CREATE FULLTEXT INDEX document_title_fts IF NOT EXISTS
FOR (d:Document) ON EACH [d.title]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

// New entity FTS indexes
CREATE FULLTEXT INDEX person_text_fts IF NOT EXISTS
FOR (pr:Person) ON EACH [pr.text]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

CREATE FULLTEXT INDEX organization_text_fts IF NOT EXISTS
FOR (g:Organization) ON EACH [g.text]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

CREATE FULLTEXT INDEX location_text_fts IF NOT EXISTS
FOR (l:Location) ON EACH [l.text]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'english', `fulltext.eventually_consistent`: true } };

/// ---- Param for the CSV file name ----
:param csvFile => 'all_pdfs_related_alternatives.csv';

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
  trim(coalesce(row.loc,''))          AS loc_text
  ,  trim(coalesce(row.org_alternative,'')) AS org_alt_text,  trim(coalesce(row.loc_alternative,'')) AS loc_alt_text,  trim(coalesce(row.per_alternative,'')) AS per_alt_text,  trim(coalesce(row.subject_text_alternative,'')) AS subject_text_alt_text,  trim(coalesce(row.org_alternative_taxonomy,'')) AS org_alt_tax_text,  trim(coalesce(row.loc_alternative_taxonomy,'')) AS loc_alt_tax_text,  trim(coalesce(row.per_alternative_taxonomy,'')) AS per_alt_tax_text,  trim(coalesce(row.subject_text_alternative_taxonomy,'')) AS subject_text_alt_tax_text

WITH
  row, s_type, o_type, rel_lc, s_text, o_text, file, title, textBlock, effect_size, page, avg_confidence,
  per_text, org_text, loc_text,
  org_alt_text, loc_alt_text, per_alt_text, subject_text_alt_text, org_alt_tax_text, loc_alt_tax_text, per_alt_tax_text, subject_text_alt_tax_text, 
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
  CASE WHEN loc_text = '' THEN [] ELSE [t IN split(loc_text, ';') WHERE trim(t) <> '' | trim(t)] END AS loc_list,  CASE WHEN org_alt_text = '' THEN [] ELSE [t IN split(org_alt_text, ';') | trim(t)] END AS org_alt_list,  CASE WHEN loc_alt_text = '' THEN [] ELSE [t IN split(loc_alt_text, ';') | trim(t)] END AS loc_alt_list,  CASE WHEN per_alt_text = '' THEN [] ELSE [t IN split(per_alt_text, ';') | trim(t)] END AS per_alt_list,  CASE WHEN subject_text_alt_text = '' THEN [] ELSE [t IN split(subject_text_alt_text, ';') | trim(t)] END AS subject_text_alt_list,  CASE WHEN org_alt_tax_text = '' THEN [] ELSE [t IN split(org_alt_tax_text, ';') | trim(t)] END AS org_alt_tax_list,  CASE WHEN loc_alt_tax_text = '' THEN [] ELSE [t IN split(loc_alt_tax_text, ';') | trim(t)] END AS loc_alt_tax_list,  CASE WHEN per_alt_tax_text = '' THEN [] ELSE [t IN split(per_alt_tax_text, ';') | trim(t)] END AS per_alt_tax_list,  CASE WHEN subject_text_alt_tax_text = '' THEN [] ELSE [t IN split(subject_text_alt_tax_text, ';') | trim(t)] END AS subject_text_alt_tax_list

// Document & Excerpt (provenance)
MERGE (d:Document {doc_key: doc_key})
  ON CREATE SET d.file = file, d.title = title

MERGE (x:Excerpt {excerpt_key: excerpt_key})
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

// Persons, Organizations, Locations extracted from lists
FOREACH (i IN CASE WHEN size(per_list) > 0 THEN range(0, size(per_list)-1) ELSE [] END |
  MERGE (pr:Person {unique_key: 'person|' + toLower(per_list[i])})
    ON CREATE SET pr.file = file, pr.title = per_list[i], pr.text = per_list[i], pr.type = 'person', pr.page = page_int
  MERGE (pr)-[mpr:MENTIONED_IN]->(x)
    ON CREATE SET mpr.file = file, mpr.title = title, mpr.page = page_int
  
  FOREACH (alt_per IN CASE WHEN size(per_alt_list) > i AND per_alt_list[i] <> '' THEN [per_alt_list[i]] ELSE [] END |
    MERGE (alt_pr:Person {unique_key: 'person|' + toLower(alt_per)})
      ON CREATE SET alt_pr.file = file, alt_pr.title = alt_per, alt_pr.text = alt_per, alt_pr.type = 'person', alt_pr.page = page_int
    MERGE (pr)-[:ALTERNATIVE_VOCABULARY]->(alt_pr)
    // Taxonomy chains for this alternative person (multiple paths supported)
    FOREACH (tax_path IN CASE WHEN size(per_alt_tax_list) > i AND per_alt_tax_list[i] <> '' THEN [tp IN split(per_alt_tax_list[i], '|') WHERE trim(tp) <> '' | trim(tp)] ELSE [] END |
      FOREACH (_ IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 0 THEN [1] ELSE [] END |
        MERGE (t0:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0])})
          ON CREATE SET t0.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0]
        MERGE (alt_pr)-[:IN_TAXONOMY]->(t0)
      )
      FOREACH (idx IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 1 THEN range(0, size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)])-2) ELSE [] END |
        MERGE (c:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx])})
          ON CREATE SET c.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx]
        MERGE (p:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx+1])})
          ON CREATE SET p.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx+1]
        MERGE (c)-[:IN_TAXONOMY]->(p)
      )
    )
  )
)

FOREACH (i IN CASE WHEN size(org_list) > 0 THEN range(0, size(org_list)-1) ELSE [] END |
  MERGE (g:Organization {unique_key: 'organization|' + toLower(org_list[i])})
    ON CREATE SET g.file = file, g.title = org_list[i], g.text = org_list[i], g.type = 'organization', g.page = page_int
  MERGE (g)-[mg:MENTIONED_IN]->(x)
    ON CREATE SET mg.file = file, mg.title = title, mg.page = page_int
  
  FOREACH (alt_org IN CASE WHEN size(org_alt_list) > i AND org_alt_list[i] <> '' THEN [org_alt_list[i]] ELSE [] END |
    MERGE (alt_g:Organization {unique_key: 'organization|' + toLower(alt_org)})
      ON CREATE SET alt_g.file = file, alt_g.title = alt_org, alt_g.text = alt_org, alt_g.type = 'organization', alt_g.page = page_int
    MERGE (g)-[:ALTERNATIVE_VOCABULARY]->(alt_g)
    // Taxonomy chains for this alternative organization (multiple paths supported)
    FOREACH (tax_path IN CASE WHEN size(org_alt_tax_list) > i AND org_alt_tax_list[i] <> '' THEN [tp IN split(org_alt_tax_list[i], '|') WHERE trim(tp) <> '' | trim(tp)] ELSE [] END |
      FOREACH (_ IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 0 THEN [1] ELSE [] END |
        MERGE (t0:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0])})
          ON CREATE SET t0.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0]
        MERGE (alt_g)-[:IN_TAXONOMY]->(t0)
      )
      FOREACH (idx IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 1 THEN range(0, size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)])-2) ELSE [] END |
        MERGE (c:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx])})
          ON CREATE SET c.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx]
        MERGE (p:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx+1])})
          ON CREATE SET p.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx+1]
        MERGE (c)-[:IN_TAXONOMY]->(p)
      )
    )
  )
)

FOREACH (i IN CASE WHEN size(loc_list) > 0 THEN range(0, size(loc_list)-1) ELSE [] END |
  MERGE (l:Location {unique_key: 'location|' + toLower(loc_list[i])})
    ON CREATE SET l.file = file, l.title = loc_list[i], l.text = loc_list[i], l.type = 'location', l.page = page_int
  MERGE (l)-[ml:MENTIONED_IN]->(x)
    ON CREATE SET ml.file = file, ml.title = title, ml.page = page_int
  
  FOREACH (alt_loc IN CASE WHEN size(loc_alt_list) > i AND loc_alt_list[i] <> '' THEN [loc_alt_list[i]] ELSE [] END |
    MERGE (alt_l:Location {unique_key: 'location|' + toLower(alt_loc)})
      ON CREATE SET alt_l.file = file, alt_l.title = alt_loc, alt_l.text = alt_loc, alt_l.type = 'location', alt_l.page = page_int
    MERGE (l)-[:ALTERNATIVE_VOCABULARY]->(alt_l)
    // Taxonomy chains for this alternative location (multiple paths supported)
    FOREACH (tax_path IN CASE WHEN size(loc_alt_tax_list) > i AND loc_alt_tax_list[i] <> '' THEN [tp IN split(loc_alt_tax_list[i], '|') WHERE trim(tp) <> '' | trim(tp)] ELSE [] END |
      FOREACH (_ IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 0 THEN [1] ELSE [] END |
        MERGE (t0:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0])})
          ON CREATE SET t0.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0]
        MERGE (alt_l)-[:IN_TAXONOMY]->(t0)
      )
      FOREACH (idx IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 1 THEN range(0, size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)])-2) ELSE [] END |
        MERGE (c:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx])})
          ON CREATE SET c.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx]
        MERGE (p:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx+1])})
          ON CREATE SET p.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][idx+1]
        MERGE (c)-[:IN_TAXONOMY]->(p)
      )
    )
  )
)

// Subject Node (direct type creation)
FOREACH (_ IN CASE WHEN s_type = 'intervention' THEN [1] ELSE [] END |
  MERGE (s:Intervention {unique_key: s_key})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)
FOREACH (_ IN CASE WHEN s_type = 'outcome' THEN [1] ELSE [] END |
  MERGE (s:Outcome {unique_key: s_key})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)
FOREACH (_ IN CASE WHEN s_type = 'population' THEN [1] ELSE [] END |
  MERGE (s:Population {unique_key: s_key})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)
FOREACH (_ IN CASE WHEN s_type = 'coreference' THEN [1] ELSE [] END |
  MERGE (s:Coreference {unique_key: s_key})
    ON CREATE SET
      s.file = file,
      s.title = s_text,
      s.text = s_text,
      s.type = s_type,
      s.page = page_int
)

// Object Node (direct type creation)
FOREACH (_ IN CASE WHEN o_type = 'intervention' THEN [1] ELSE [] END |
  MERGE (o:Intervention {unique_key: o_key})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)
FOREACH (_ IN CASE WHEN o_type = 'outcome' THEN [1] ELSE [] END |
  MERGE (o:Outcome {unique_key: o_key})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)
FOREACH (_ IN CASE WHEN o_type = 'population' THEN [1] ELSE [] END |
  MERGE (o:Population {unique_key: o_key})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)
FOREACH (_ IN CASE WHEN o_type = 'coreference' THEN [1] ELSE [] END |
  MERGE (o:Coreference {unique_key: o_key})
    ON CREATE SET
      o.file = file,
      o.title = o_text,
      o.text = o_text,
      o.type = o_type,
      o.page = page_int
)

// Get references to subject and object nodes for relationships
WITH row, s_type, o_type, rel_lc, s_key, o_key, file, title, textBlock, effect_size, page, page_int, avg_confidence, d, x, subject_text_alt_list, subject_text_alt_tax_list
OPTIONAL MATCH (s) WHERE s.unique_key = s_key
OPTIONAL MATCH (o) WHERE o.unique_key = o_key


// Subject alternatives from subject_text alternative list
FOREACH (i IN CASE WHEN size(subject_text_alt_list) > 0 THEN range(0, size(subject_text_alt_list)-1) ELSE [] END |
  FOREACH (_ IN CASE WHEN s_type = 'intervention' THEN [1] ELSE [] END |
    MERGE (alt_s:Intervention {unique_key: 'intervention|' + toLower(subject_text_alt_list[i])})
      ON CREATE SET alt_s.file = file, alt_s.title = subject_text_alt_list[i], alt_s.text = subject_text_alt_list[i], alt_s.type = 'intervention', alt_s.page = page_int
    MERGE (s)-[:ALTERNATIVE_VOCABULARY]->(alt_s)
    FOREACH (tax_path IN CASE WHEN size(subject_text_alt_tax_list) > i AND subject_text_alt_tax_list[i] <> '' THEN [tp IN split(subject_text_alt_tax_list[i], '|') WHERE trim(tp) <> '' | trim(tp)] ELSE [] END |
      FOREACH (__ IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 0 THEN [1] ELSE [] END |
        MERGE (t0:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0])})
          ON CREATE SET t0.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0]
        MERGE (alt_s)-[:IN_TAXONOMY]->(t0)
      )
      FOREACH (j IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 1 THEN range(0, size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)])-2) ELSE [] END |
        MERGE (c:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j])})
          ON CREATE SET c.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j]
        MERGE (p:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1])})
          ON CREATE SET p.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1]
        MERGE (c)-[:IN_TAXONOMY]->(p)
      )
    )
  )
  FOREACH (_ IN CASE WHEN s_type = 'outcome' THEN [1] ELSE [] END |
    MERGE (alt_s:Outcome {unique_key: 'outcome|' + toLower(subject_text_alt_list[i])})
      ON CREATE SET alt_s.file = file, alt_s.title = subject_text_alt_list[i], alt_s.text = subject_text_alt_list[i], alt_s.type = 'outcome', alt_s.page = page_int
    MERGE (s)-[:ALTERNATIVE_VOCABULARY]->(alt_s)
    FOREACH (tax_path IN CASE WHEN size(subject_text_alt_tax_list) > i AND subject_text_alt_tax_list[i] <> '' THEN [tp IN split(subject_text_alt_tax_list[i], '|') WHERE trim(tp) <> '' | trim(tp)] ELSE [] END |
      FOREACH (__ IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 0 THEN [1] ELSE [] END |
        MERGE (t0:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0])})
          ON CREATE SET t0.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0]
        MERGE (alt_s)-[:IN_TAXONOMY]->(t0)
      )
      FOREACH (j IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 1 THEN range(0, size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)])-2) ELSE [] END |
        MERGE (c:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j])})
          ON CREATE SET c.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j]
        MERGE (p:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1])})
          ON CREATE SET p.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1]
        MERGE (c)-[:IN_TAXONOMY]->(p)
      )
    )
  )
  FOREACH (_ IN CASE WHEN s_type = 'population' THEN [1] ELSE [] END |
    MERGE (alt_s:Population {unique_key: 'population|' + toLower(subject_text_alt_list[i])})
      ON CREATE SET alt_s.file = file, alt_s.title = subject_text_alt_list[i], alt_s.text = subject_text_alt_list[i], alt_s.type = 'population', alt_s.page = page_int
    MERGE (s)-[:ALTERNATIVE_VOCABULARY]->(alt_s)
    FOREACH (tax_path IN CASE WHEN size(subject_text_alt_tax_list) > i AND subject_text_alt_tax_list[i] <> '' THEN [tp IN split(subject_text_alt_tax_list[i], '|') WHERE trim(tp) <> '' | trim(tp)] ELSE [] END |
      FOREACH (__ IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 0 THEN [1] ELSE [] END |
        MERGE (t0:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0])})
          ON CREATE SET t0.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0]
        MERGE (alt_s)-[:IN_TAXONOMY]->(t0)
      )
      FOREACH (j IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 1 THEN range(0, size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)])-2) ELSE [] END |
        MERGE (c:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j])})
          ON CREATE SET c.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j]
        MERGE (p:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1])})
          ON CREATE SET p.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1]
        MERGE (c)-[:IN_TAXONOMY]->(p)
      )
    )
  )
  FOREACH (_ IN CASE WHEN s_type = 'coreference' THEN [1] ELSE [] END |
    MERGE (alt_s:Coreference {unique_key: 'coreference|' + toLower(subject_text_alt_list[i])})
      ON CREATE SET alt_s.file = file, alt_s.title = subject_text_alt_list[i], alt_s.text = subject_text_alt_list[i], alt_s.type = 'coreference', alt_s.page = page_int
    MERGE (s)-[:ALTERNATIVE_VOCABULARY]->(alt_s)
    FOREACH (tax_path IN CASE WHEN size(subject_text_alt_tax_list) > i AND subject_text_alt_tax_list[i] <> '' THEN [tp IN split(subject_text_alt_tax_list[i], '|') WHERE trim(tp) <> '' | trim(tp)] ELSE [] END |
      FOREACH (__ IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 0 THEN [1] ELSE [] END |
        MERGE (t0:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0])})
          ON CREATE SET t0.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][0]
        MERGE (alt_s)-[:IN_TAXONOMY]->(t0)
      )
      FOREACH (j IN CASE WHEN size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)]) > 1 THEN range(0, size([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)])-2) ELSE [] END |
        MERGE (c:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j])})
          ON CREATE SET c.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j]
        MERGE (p:Taxon {unique_key: 'taxon|' + toLower([lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1])})
          ON CREATE SET p.title = [lv IN split(tax_path, '->') WHERE trim(lv) <> '' | trim(lv)][j+1]
        MERGE (c)-[:IN_TAXONOMY]->(p)
      )
    )
  )
)


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
