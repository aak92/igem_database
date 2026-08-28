"""ETL Step 1: Load compound table."""
import pandas as pd
from sqlalchemy import create_engine, text
from config import DATA_DIR, DB_URL

engine = create_engine(DB_URL)

EXCLUDED_COMMON_COMPOUND_IDS = {"CHEBI:15377", "CHEBI:15378", "CHEBI:33019"}

COMPOUND_COLUMNS = {
    "inchi_key": "VARCHAR(100)",
}


def _ensure_columns(table_name, columns):
    with engine.connect() as conn:
        for column_name, ddl in columns.items():
            exists = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() "
                    "AND table_name = :table_name AND column_name = :column_name"
                ),
                {"table_name": table_name, "column_name": column_name},
            ).scalar()
            if not exists:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
        conn.commit()


def load_compounds():
    _ensure_columns("compound", COMPOUND_COLUMNS)
    compounds_path = f"{DATA_DIR}/for_compound_card/uniprotkb_terpene_compounds.tsv"
    df = pd.read_csv(compounds_path, sep="\t")
    df = df[~df["ChEBI ID"].isin(EXCLUDED_COMMON_COMPOUND_IDS)]

    df["compound_id"] = df["ChEBI ID"]
    df["name"] = df["Name"]
    df["chebi_id"] = df["ChEBI ID"]
    df["smiles"] = df["SMILES"]
    df["average_mass"] = pd.to_numeric(df["Molecular Mass"], errors="coerce")
    df["chebi_url"] = df["ChEBI URL"]
    df["inchi_key"] = None
    df["structure_image_url"] = df["ChEBI ID"].apply(
        lambda x: f"https://www.ebi.ac.uk/chebi/displayImage.do?defaultImage=true&chebiId={x.split(':')[-1]}"
    )

    cols = ["compound_id", "name", "chebi_id", "smiles", "average_mass",
            "chebi_url", "inchi_key", "structure_image_url"]
    df[cols].to_sql("compound", engine, if_exists="append", index=False)
    print(f"  compound: {len(df)} rows inserted")


def supplement_from_all_nodes():
    """Add any compounds from all_nodes.tsv that aren't already in the table."""
    _ensure_columns("compound", COMPOUND_COLUMNS)
    all_nodes_path = f"{DATA_DIR}/for_graph/all_nodes.tsv"
    df = pd.read_csv(all_nodes_path, sep="\t")
    df = df[~df["ChEBI ID"].isin(EXCLUDED_COMMON_COMPOUND_IDS)]

    existing = pd.read_sql("SELECT compound_id FROM compound", engine)
    existing_ids = set(existing["compound_id"])

    has_inchi_key = "InChI Key" in df.columns
    update_rows = df[df["ChEBI ID"].isin(existing_ids) & df["InChI Key"].notna()] if has_inchi_key else df.iloc[0:0]
    if len(update_rows) > 0:
        with engine.connect() as conn:
            for _, row in update_rows.iterrows():
                inchi_key = str(row.get("InChI Key", "")).strip()
                if inchi_key:
                    conn.execute(
                        text("UPDATE compound SET inchi_key = :inchi_key WHERE compound_id = :compound_id"),
                        {"inchi_key": inchi_key, "compound_id": row["ChEBI ID"]},
                    )
            conn.commit()

    new_rows = df[~df["ChEBI ID"].isin(existing_ids)]
    if len(new_rows) == 0:
        print(f"  (no new compounds from all_nodes.tsv)")
        return

    insert = pd.DataFrame({
        "compound_id": new_rows["ChEBI ID"],
        "name": new_rows["Name"],
        "chebi_id": new_rows["ChEBI ID"],
        "inchi_key": new_rows["InChI Key"] if has_inchi_key else None,
    })
    insert.to_sql("compound", engine, if_exists="append", index=False)
    print(f"  compound (from all_nodes): {len(insert)} new rows")


if __name__ == "__main__":
    load_compounds()
    supplement_from_all_nodes()


def run():
    load_compounds()
    supplement_from_all_nodes()
