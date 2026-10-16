# Real sewer network, Odense: what to build

The published EPA SWMM model of the Bellinge combined sewer system in Odense, Denmark (Pedersen et al., 2021, CC BY 4.0), run on eight real storms. Your water levels are compared with seven level meters.

## Build
- The model: `model/BellingeSWMM_v021_nopervious_2012-06-29.inp` (the storm of 29 June 2012). It reads the rain file `rg_bellinge_Jun2010_Aug2021.dat`, which comes with the model from DTU Data (doi:10.11583/DTU.12513428, item 7_SWMM); put it next to the .inp.
- Run it unchanged, apart from the dates. The eight storms and their dates are listed in `manifest.json` (`simulation.events`): each run starts 12 hours before the storm's day and ends 48 hours after its start.

## Run
One run per storm. Report the water depth at the seven level-meter nodes every minute.
