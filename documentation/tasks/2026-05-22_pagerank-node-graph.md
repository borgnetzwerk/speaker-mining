# pagerank-node-graph

* priority: medium
* scope: pipeline
* legacy-id: TODO-032

## Summary

The current page rank chart in `51_visualization.ipynb` is a bar chart, but page rank was designed to be visualized as a node graph. Bar charts are a poor fit for page rank output and should be replaced.

## Evidence

`speakermining/src/process/notebooks/51_visualization.ipynb`.

## Definition of done

1. The bar-chart page rank visualization is removed from `51_visualization.ipynb`.
2. A node-graph visualization of page rank is implemented, showing nodes sized or colored by their rank score.
3. The new visualization is exported as PNG + PDF to `data/output/visualization`.
