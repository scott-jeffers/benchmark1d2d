# A1F-043 — Lake at rest with an emerged bump (SWASHES)

## Physics

Still water at level 0.1 m over the same bump, whose top (0.2 m) stands out
of the water between \(x = 10 - \sqrt{2} = 8.586\) and \(10 + \sqrt{2} = 11.414\) m. The exact solution is the
initial state: \(h = \max(0.1 - z, 0)\), \(u = 0\), for all time.

## What it checks

Well-balancing (the discrete bed-slope source must cancel the discrete
pressure gradient exactly in still water) and the treatment of a dry
shoreline on a slope. Velocities must stay under 1 mm/s and the average depth
change under 0.5 mm. The worst depth difference is reported but does not
decide the result: in the cells cut by the shoreline, a cell-mean depth over
the sloping bump differs from the exact depth at the cell centre even when
nothing moves.

## Citation

Delestre et al. (2013), SWASHES, doi:10.1002/fld.3741.
