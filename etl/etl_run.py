"""ETL Runner — execute all ETL steps in dependency order."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import etl_compounds
import etl_enzymes
import etl_reactions
import etl_edges
import etl_master
import etl_search_index

STEPS = [
    ("1/6 compounds", etl_compounds.run),
    ("2/6 enzymes", etl_enzymes.run),
    ("3/6 reactions", etl_reactions.run),
    ("4/6 edges", etl_edges.run),
    ("5/6 master (sequence + gene + evidence + GO + isoforms)", etl_master.run),
    ("6/6 search index", etl_search_index.run),
]

if __name__ == "__main__":
    for label, fn in STEPS:
        print(f"\n[{label}]")
        try:
            fn()
            print(f"[{label}] OK")
        except Exception as e:
            print(f"[{label}] FAILED: {e}")
            sys.exit(1)

    print("\n=== ETL complete ===")
