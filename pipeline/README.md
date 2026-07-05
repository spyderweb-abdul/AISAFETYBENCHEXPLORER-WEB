# Pipeline Package (imported, not rewritten)

This directory is a placeholder for the existing AISAFETYBENCHEXPLORER
GitHub repo, imported as an editable Python package:

    pip install -e ./pipeline

Only these modules remain as deterministic tools called by the
orchestration agent in Phase 3:

- doi_based_resolver.py
- github_scrapper.py
- hf_scrapper.py
- repo_extractor.py
- models.py

Clone the actual repo content here before Phase 3 begins:

    git clone https://github.com/spyderweb-abdul/AISAFETYBENCHEXPLORER.git pipeline
