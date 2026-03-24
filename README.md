# Lanz-Mining but FAIR

This repository contains a notebook-first workflow for extracting, enriching, disambiguating, deduplicating, and inferring structured talk show knowledge.

## What Is This?

Speaker Mining pipeline implementation for research-oriented curation of talk show data.

The workflow is phase-based and human-in-the-loop where precision matters most:

1. mention detection
2. candidate generation
3. entity disambiguation (manual decisions)
4. entity deduplication (manual decisions)
5. link prediction

## Background

This repository continues prior work from LanzMining, Lanz Mining but FAIR, and related linked-data/media analyses.

See the dedicated background page:

* [documentation/background.md](documentation/background.md)

## Usage

Run the phase notebooks in order:

1. [speakermining/src/process/notebooks/10_mention_detection.ipynb](speakermining/src/process/notebooks/10_mention_detection.ipynb)
2. [speakermining/src/process/notebooks/20_candidate_generation.ipynb](speakermining/src/process/notebooks/20_candidate_generation.ipynb)
3. [speakermining/src/process/notebooks/30_entity_disambiguation.ipynb](speakermining/src/process/notebooks/30_entity_disambiguation.ipynb)
4. [speakermining/src/process/notebooks/31_entity_deduplication.ipynb](speakermining/src/process/notebooks/31_entity_deduplication.ipynb)
5. [speakermining/src/process/notebooks/40_link_prediction.ipynb](speakermining/src/process/notebooks/40_link_prediction.ipynb)

Each phase writes only to its owned folder under `data/`.

## Additional Documentation

Use the documentation to navigate detailed docs:

* [documentation/README.md](documentation/README.md)

## Citation

If you cite the methodological lineage, please reference:

```
@article{remmo_lanzmining_2026,
	title = {{LanzMining} aber {FAIR}: {Empirische} {Fragen} zur {Medienlandschaft} mittels {FAIRer} {Talkshow}-{Daten} beantworten},
	shorttitle = {{LanzMining} aber {FAIR}},
	url = {https://repo.uni-hannover.de/handle/123456789/20906},
	doi = {10.15488/20751},
	language = {ger},
	author = {Remmo, Omar Imad},
	publisher = {Hannover : Institutionelles Repositorium der Leibniz Universität Hannover},
	year = {2026},
	month = mar,
}
```
