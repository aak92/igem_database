"""ETL Step 6: Build a broad search index from all TSV sources."""
import hashlib
import os
import re

import pandas as pd
from sqlalchemy import create_engine, text

from config import DATA_DIR, DB_URL

engine = create_engine(DB_URL)

COMPOUND_FILE = os.path.join(DATA_DIR, "for_compound_card", "uniprotkb_terpene_compounds.tsv")
ALL_NODES_FILE = os.path.join(DATA_DIR, "for_graph", "all_nodes.tsv")
TERPENE_ONLY_FILE = os.path.join(DATA_DIR, "for_graph", "uniprotkb_terpene_only.tsv")
TERPENE_PAIRS_FILE = os.path.join(DATA_DIR, "for_graph", "uniprotkb_terpene_pairs.tsv")
RHEA_SUMMARY_FILE = os.path.join(DATA_DIR, "for_enzyme_reation_card", "uniprotkb_rhea_summary.tsv")
ENZYME_MERGED_FILE = os.path.join(DATA_DIR, "for_enzyme_reation_card", "uniprotkb_enzyme_merged.tsv")
MASTER_FILE = os.path.join(DATA_DIR, "for_enzyme_detail", "uniprotkb_master.tsv")
NAMES_FILE = os.path.join(DATA_DIR, "for_enzyme_detail", "child_tables", "uniprotkb_names_split.tsv")
RHEA_FILE = os.path.join(DATA_DIR, "for_enzyme_detail", "child_tables", "uniprotkb_rhea.tsv")
REFERENCES_FILE = os.path.join(DATA_DIR, "for_enzyme_detail", "child_tables", "uniprotkb_references.tsv")
SEQ_LINKS_FILE = os.path.join(DATA_DIR, "for_enzyme_detail", "child_tables", "uniprotkb_sequence_links.tsv")
GO_FILE = os.path.join(DATA_DIR, "for_enzyme_detail", "child_tables", "uniprotkb_go.tsv")
ISOFORM_FILE = os.path.join(DATA_DIR, "for_enzyme_detail", "child_tables", "uniprotkb_isoform_sequences.tsv")
EXCLUDED_COMMON_COMPOUND_IDS = {"CHEBI:15377", "CHEBI:15378", "CHEBI:33019"}


SEARCH_INDEX_DDL = """
CREATE TABLE IF NOT EXISTS search_index (
    search_index_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(30) NOT NULL,
    entity_id VARCHAR(80) NOT NULL,
    enzyme_id VARCHAR(20),
    source_file VARCHAR(160) NOT NULL,
    field_name VARCHAR(80) NOT NULL,
    field_value TEXT NOT NULL,
    field_value_hash CHAR(40) NOT NULL,
    weight INT NOT NULL DEFAULT 10,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_search_index_entity (entity_type, entity_id),
    INDEX idx_search_index_enzyme (enzyme_id),
    INDEX idx_search_index_field (field_name),
    INDEX idx_search_index_hash (field_value_hash),
    CONSTRAINT fk_search_index_enzyme
        FOREIGN KEY (enzyme_id) REFERENCES enzyme(enzyme_id)
)
"""


def _clean(value):
    if pd.isna(value):
        return None
    text_value = str(value).strip()
    if not text_value or text_value == "-":
        return None
    return text_value


def _hash(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _source(path):
    return os.path.relpath(path, DATA_DIR).replace("\\", "/")


def _add(rows, entity_type, entity_id, enzyme_id, source_file, field_name, value, weight):
    value = _clean(value)
    entity_id = _clean(entity_id)
    if not value or not entity_id:
        return
    if entity_type == "compound" and entity_id in EXCLUDED_COMMON_COMPOUND_IDS:
        return
    rows.append({
        "entity_type": entity_type,
        "entity_id": entity_id,
        "enzyme_id": _clean(enzyme_id),
        "source_file": _source(source_file),
        "field_name": field_name,
        "field_value": value,
        "field_value_hash": _hash(value.lower()),
        "weight": weight,
    })


def _read(path, **kwargs):
    return pd.read_csv(path, sep="\t", dtype=str, **kwargs)


def _get_map(table, external_col, internal_col):
    try:
        df = pd.read_sql(f"SELECT {external_col}, {internal_col} FROM {table}", engine)
    except Exception:
        return {}
    return {
        str(row[external_col]).strip(): str(row[internal_col]).strip()
        for _, row in df.iterrows()
        if _clean(row.get(external_col)) and _clean(row.get(internal_col))
    }


def _indexed_groups(columns, stem):
    numbers = []
    pattern = re.compile(rf"^{re.escape(stem)}_(\d+)$")
    for col in columns:
        match = pattern.match(col)
        if match:
            numbers.append(int(match.group(1)))
    return range(1, max(numbers, default=0) + 1)


def _filter_chebi_ids(value):
    value = _clean(value)
    if not value:
        return None
    ids = [
        chebi_id for chebi_id in re.findall(r"CHEBI:\d+", value)
        if chebi_id not in EXCLUDED_COMMON_COMPOUND_IDS
    ]
    return "; ".join(dict.fromkeys(ids)) if ids else None


def _add_enzyme_file(rows, path, entry_to_enzyme_id):
    df = _read(path)
    fields = [
        ("Entry", "uniprot_id", 95),
        ("UniProt Link", "uniprot_url", 35),
        ("Entry Name", "entry_name", 65),
        ("Organism", "organism", 35),
        ("Recommended name", "primary_name", 65),
        ("Recommended Name", "primary_name", 65),
        ("Protein name", "primary_name", 60),
        ("Alternative names", "alternative_names", 45),
    ]
    for _, row in df.iterrows():
        entry = _clean(row.get("Entry"))
        enzyme_id = entry_to_enzyme_id.get(entry)
        if not enzyme_id:
            continue
        for column, field_name, weight in fields:
            if column in df.columns:
                _add(rows, "enzyme", enzyme_id, enzyme_id, path, field_name, row.get(column), weight)


def _compound_to_enzyme_ids(entry_to_enzyme_id):
    mapping = {}
    if os.path.exists(TERPENE_ONLY_FILE):
        df = _read(TERPENE_ONLY_FILE)
        for _, row in df.iterrows():
            enzyme_id = entry_to_enzyme_id.get(_clean(row.get("Entry")))
            if not enzyme_id:
                continue
            for column in ("Substrate ChEBI", "Product ChEBI"):
                compound_id = _clean(row.get(column))
                if compound_id and compound_id not in EXCLUDED_COMMON_COMPOUND_IDS:
                    mapping.setdefault(compound_id, set()).add(enzyme_id)

    if os.path.exists(TERPENE_PAIRS_FILE):
        df = _read(TERPENE_PAIRS_FILE)
        for _, row in df.iterrows():
            compound_ids = [
                _clean(row.get("Substrate ChEBI")),
                _clean(row.get("Product ChEBI")),
            ]
            compound_ids = [
                compound_id for compound_id in compound_ids
                if compound_id and compound_id not in EXCLUDED_COMMON_COMPOUND_IDS
            ]
            if not compound_ids:
                continue
            for index in _indexed_groups(df.columns, "Enzyme"):
                enzyme_id = entry_to_enzyme_id.get(_clean(row.get(f"Enzyme_{index}")))
                if not enzyme_id:
                    continue
                for compound_id in compound_ids:
                    mapping.setdefault(compound_id, set()).add(enzyme_id)

    return mapping


def _add_compounds(rows, path, compound_to_enzyme_ids):
    df = _read(path)
    fields = [
        ("ChEBI ID", "compound_id", 85),
        ("ChEBI ID", "chebi_id", 85),
        ("Name", "compound_name", 65),
        ("SMILES", "smiles", 30),
        ("Molecular Mass", "average_mass", 20),
        ("ChEBI URL", "chebi_url", 25),
        ("InChI Key", "inchi_key", 50),
    ]
    for _, row in df.iterrows():
        compound_id = _clean(row.get("ChEBI ID"))
        if not compound_id:
            continue
        for column, field_name, weight in fields:
            if column in df.columns:
                _add(rows, "compound", compound_id, None, path, field_name, row.get(column), weight)
                for enzyme_id in compound_to_enzyme_ids.get(compound_id, set()):
                    _add(rows, "compound", compound_id, enzyme_id, path, field_name, row.get(column), weight)


def _add_rhea_rows(rows, path, entry_to_enzyme_id, rhea_to_reaction_id):
    df = _read(path)
    for _, row in df.iterrows():
        entry = _clean(row.get("Entry"))
        enzyme_id = entry_to_enzyme_id.get(entry)
        rhea_id = _clean(row.get("Rhea ID"))
        reaction_id = rhea_to_reaction_id.get(rhea_id, rhea_id)
        if not enzyme_id:
            continue
        _add(rows, "enzyme", enzyme_id, enzyme_id, path, "uniprot_id", entry, 95)
        _add(rows, "reaction", reaction_id, enzyme_id, path, "rhea_id", rhea_id, 90)
        _add(rows, "reaction", reaction_id, enzyme_id, path, "ec_number", row.get("EC Number") or row.get("EC number"), 70)
        _add(rows, "reaction", reaction_id, enzyme_id, path, "reaction_equation", row.get("Equation"), 55)
        _add(rows, "reaction", reaction_id, enzyme_id, path, "reaction_direction", row.get("Direction"), 25)
        _add(rows, "reaction", reaction_id, enzyme_id, path, "reaction_smiles", row.get("Reaction SMILES"), 30)
        _add(rows, "reaction", reaction_id, enzyme_id, path, "chebi_ids", _filter_chebi_ids(row.get("ChEBI IDs (equation order)")), 40)


def _add_terpene_only(rows, path, entry_to_enzyme_id, rhea_to_reaction_id):
    df = _read(path)
    for _, row in df.iterrows():
        enzyme_id = entry_to_enzyme_id.get(_clean(row.get("Entry")))
        reaction_id = rhea_to_reaction_id.get(_clean(row.get("Rhea ID")), _clean(row.get("Rhea ID")))
        if not enzyme_id:
            continue
        _add(rows, "reaction", reaction_id, enzyme_id, path, "rhea_id", row.get("Rhea ID"), 90)
        _add(rows, "compound", row.get("Substrate ChEBI"), enzyme_id, path, "substrate_chebi", row.get("Substrate ChEBI"), 80)
        _add(rows, "compound", row.get("Substrate ChEBI"), enzyme_id, path, "substrate", row.get("Substrate"), 60)
        _add(rows, "compound", row.get("Product ChEBI"), enzyme_id, path, "product_chebi", row.get("Product ChEBI"), 80)
        _add(rows, "compound", row.get("Product ChEBI"), enzyme_id, path, "product", row.get("Product"), 60)
        _add(rows, "reaction", reaction_id, enzyme_id, path, "reaction_direction", row.get("Direction"), 25)


def _add_terpene_pairs(rows, path, entry_to_enzyme_id, rhea_to_reaction_id):
    df = _read(path)
    for _, row in df.iterrows():
        for index in _indexed_groups(df.columns, "Enzyme"):
            enzyme_entry = _clean(row.get(f"Enzyme_{index}"))
            enzyme_id = entry_to_enzyme_id.get(enzyme_entry)
            if not enzyme_id:
                continue
            rhea_id = _clean(row.get(f"Rhea ID_{index}"))
            reaction_id = rhea_to_reaction_id.get(rhea_id, rhea_id)
            _add(rows, "enzyme", enzyme_id, enzyme_id, path, "uniprot_id", enzyme_entry, 95)
            _add(rows, "reaction", reaction_id, enzyme_id, path, "rhea_id", rhea_id, 90)
            _add(rows, "compound", row.get("Substrate ChEBI"), enzyme_id, path, "substrate_chebi", row.get("Substrate ChEBI"), 80)
            _add(rows, "compound", row.get("Substrate ChEBI"), enzyme_id, path, "substrate", row.get("Substrate"), 60)
            _add(rows, "compound", row.get("Product ChEBI"), enzyme_id, path, "product_chebi", row.get("Product ChEBI"), 80)
            _add(rows, "compound", row.get("Product ChEBI"), enzyme_id, path, "product", row.get("Product"), 60)
            _add(rows, "reaction", reaction_id, enzyme_id, path, "reaction_direction", row.get(f"Direction_{index}"), 25)


def _add_references(rows, path, entry_to_enzyme_id):
    df = _read(path)
    for _, row in df.iterrows():
        enzyme_id = entry_to_enzyme_id.get(_clean(row.get("Entry")))
        if not enzyme_id:
            continue
        for index in _indexed_groups(df.columns, "PMID"):
            ref_entity = _clean(row.get(f"PMID_{index}")) or _clean(row.get(f"DOI_{index}")) or f"{enzyme_id}:reference:{index}"
            for column, field_name, weight in [
                (f"PMID_{index}", "pubmed_id", 80),
                (f"DOI_{index}", "doi", 80),
                (f"Title_{index}", "reference_title", 55),
                (f"Authors_{index}", "reference_authors", 35),
                (f"Journal_{index}", "journal", 35),
                (f"Volume_{index}", "volume", 15),
                (f"Pages_{index}", "pages", 15),
                (f"Year_{index}", "year", 25),
                (f"Type_{index}", "reference_type", 25),
                (f"Positions_{index}", "evidence_positions", 35),
                (f"URL_{index}", "reference_url", 25),
            ]:
                _add(rows, "evidence", ref_entity, enzyme_id, path, field_name, row.get(column), weight)


def _add_go(rows, path, entry_to_enzyme_id):
    df = _read(path)
    for _, row in df.iterrows():
        enzyme_id = entry_to_enzyme_id.get(_clean(row.get("Entry")))
        if not enzyme_id:
            continue
        go_id = _clean(row.get("GO ID")) or f"{enzyme_id}:go"
        _add(rows, "go", go_id, enzyme_id, path, "go_id", row.get("GO ID"), 75)
        _add(rows, "go", go_id, enzyme_id, path, "go_term", row.get("GO Term"), 55)
        _add(rows, "go", go_id, enzyme_id, path, "go_url", row.get("GO Link"), 20)


def _add_sequence_links(rows, path, entry_to_enzyme_id):
    df = _read(path)
    for _, row in df.iterrows():
        enzyme_id = entry_to_enzyme_id.get(_clean(row.get("Entry")))
        if not enzyme_id:
            continue
        for index in range(1, 25):
            nuc_id = _clean(row.get(f"INSDC_Nuc_ID_{index}"))
            prot_id = _clean(row.get(f"INSDC_Prot_ID_{index}"))
            molecule = row.get(f"INSDC_Molecule_{index}")
            _add(rows, "sequence_link", nuc_id, enzyme_id, path, "accession", nuc_id, 70)
            _add(rows, "sequence_link", nuc_id, enzyme_id, path, "sequence_source", "INSDC nucleotide", 25)
            _add(rows, "sequence_link", nuc_id, enzyme_id, path, "molecule_type", molecule, 25)
            for link_col in ("EMBL", "GenBank", "DDBJ"):
                _add(rows, "sequence_link", nuc_id, enzyme_id, path, "sequence_url", row.get(f"INSDC_Nuc_{link_col}_Link_{index}"), 15)
            _add(rows, "sequence_link", prot_id, enzyme_id, path, "accession", prot_id, 70)
            _add(rows, "sequence_link", prot_id, enzyme_id, path, "sequence_source", "INSDC protein", 25)
            _add(rows, "sequence_link", prot_id, enzyme_id, path, "molecule_type", molecule, 25)
            for link_col in ("EMBL", "GenBank", "DDBJ"):
                _add(rows, "sequence_link", prot_id, enzyme_id, path, "sequence_url", row.get(f"INSDC_Prot_{link_col}_Link_{index}"), 15)

        for index in range(1, 12):
            prot_id = _clean(row.get(f"RefSeq_Prot_ID_{index}"))
            nuc_id = _clean(row.get(f"RefSeq_Nuc_ID_{index}"))
            molecule = row.get(f"RefSeq_Molecule_{index}")
            _add(rows, "sequence_link", prot_id, enzyme_id, path, "accession", prot_id, 70)
            _add(rows, "sequence_link", prot_id, enzyme_id, path, "sequence_source", "RefSeq protein", 25)
            _add(rows, "sequence_link", prot_id, enzyme_id, path, "sequence_url", row.get(f"RefSeq_Prot_Link_{index}"), 15)
            _add(rows, "sequence_link", prot_id, enzyme_id, path, "molecule_type", molecule, 25)
            _add(rows, "sequence_link", nuc_id, enzyme_id, path, "accession", nuc_id, 70)
            _add(rows, "sequence_link", nuc_id, enzyme_id, path, "sequence_source", "RefSeq nucleotide", 25)
            _add(rows, "sequence_link", nuc_id, enzyme_id, path, "sequence_url", row.get(f"RefSeq_Nuc_Link_{index}"), 15)
            _add(rows, "sequence_link", nuc_id, enzyme_id, path, "molecule_type", molecule, 25)


def _add_isoforms(rows, path, entry_to_enzyme_id):
    df = _read(path)
    for _, row in df.iterrows():
        enzyme_id = entry_to_enzyme_id.get(_clean(row.get("Entry")))
        isoform_id = _clean(row.get("Isoform_ID"))
        if not enzyme_id or not isoform_id:
            continue
        _add(rows, "isoform", isoform_id, enzyme_id, path, "isoform_id", isoform_id, 75)
        _add(rows, "isoform", isoform_id, enzyme_id, path, "isoform_length", row.get("Isoform Length"), 20)
        _add(rows, "isoform", isoform_id, enzyme_id, path, "isoform_mass", row.get("Isoform Mass"), 20)
        _add(rows, "isoform", isoform_id, enzyme_id, path, "canonical_length", row.get("Canonical Length"), 20)
        _add(rows, "isoform", isoform_id, enzyme_id, path, "canonical_mass", row.get("Canonical Mass"), 20)
        _add(rows, "isoform", isoform_id, enzyme_id, path, "canonical_sequence", row.get("Canonical Sequence"), 20)
        _add(rows, "isoform", isoform_id, enzyme_id, path, "isoform_sequence", row.get("Sequence"), 20)


def build_rows():
    entry_to_enzyme_id = _get_map("enzyme", "uniprot_id", "enzyme_id")
    rhea_to_reaction_id = _get_map("reaction", "rhea_id", "reaction_id")
    compound_to_enzyme_ids = _compound_to_enzyme_ids(entry_to_enzyme_id)
    rows = []

    for path in (NAMES_FILE, RHEA_SUMMARY_FILE, ENZYME_MERGED_FILE, MASTER_FILE):
        if os.path.exists(path):
            _add_enzyme_file(rows, path, entry_to_enzyme_id)

    for path in (COMPOUND_FILE, ALL_NODES_FILE):
        if os.path.exists(path):
            _add_compounds(rows, path, compound_to_enzyme_ids)

    if os.path.exists(RHEA_FILE):
        _add_rhea_rows(rows, RHEA_FILE, entry_to_enzyme_id, rhea_to_reaction_id)
    if os.path.exists(TERPENE_ONLY_FILE):
        _add_terpene_only(rows, TERPENE_ONLY_FILE, entry_to_enzyme_id, rhea_to_reaction_id)
    if os.path.exists(TERPENE_PAIRS_FILE):
        _add_terpene_pairs(rows, TERPENE_PAIRS_FILE, entry_to_enzyme_id, rhea_to_reaction_id)
    if os.path.exists(REFERENCES_FILE):
        _add_references(rows, REFERENCES_FILE, entry_to_enzyme_id)
    if os.path.exists(GO_FILE):
        _add_go(rows, GO_FILE, entry_to_enzyme_id)
    if os.path.exists(SEQ_LINKS_FILE):
        _add_sequence_links(rows, SEQ_LINKS_FILE, entry_to_enzyme_id)
    if os.path.exists(ISOFORM_FILE):
        _add_isoforms(rows, ISOFORM_FILE, entry_to_enzyme_id)

    return rows


def load_search_index():
    rows = build_rows()
    with engine.connect() as conn:
        conn.execute(text(SEARCH_INDEX_DDL))
        conn.execute(text("DELETE FROM search_index"))
        conn.commit()

    if not rows:
        print("  search_index: no rows to insert")
        return

    df = pd.DataFrame(rows).drop_duplicates(
        subset=["entity_type", "entity_id", "enzyme_id", "source_file", "field_name", "field_value_hash"]
    )
    df.to_sql("search_index", engine, if_exists="append", index=False, chunksize=5000)
    print(f"  search_index: {len(df)} rows inserted from all TSV sources")


if __name__ == "__main__":
    load_search_index()


def run():
    load_search_index()
