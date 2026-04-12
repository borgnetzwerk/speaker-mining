# We can

## Circular and hierarchical visualization
Current visualizations do not properly structure nodes. The goal should be to structure subclass groups together. Since any subclass may have more than one superclass, we need to funnel them together and reduce edge overlap.

For example: If 15 subclasses all have multiple connections to the same 5 superclasses, group them together. Their edges will overlap, but that is ok. If however one other other node only has a connection to one of those 5 superclasses, place it and it's superclass at the edge of this cluster - then we have one less line overlapping with that cluster. If another subclass doesn't have any connection to any of these superclasses, don't place it in the middle of these subclasses, since it line doesn't need to overlap with any of them then.
The end result should have the least amount of overlapping lines - resulting in a much cleaner image.

The same logic and sorting can be applied to several visualizations: Horizontal hierarchical clustering, radial hierarchical clustering, etc.

## Sunburst and sankey diagram
Since subclasses can have multiple superclasses, asserting them to sunburst or sankey diagrams will be difficult.