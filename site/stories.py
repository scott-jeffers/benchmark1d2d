"""Plain-language text for every test: what a non-specialist sees first.

Each entry is keyed by the short test id. The technical description, criteria
and rationale stay in the manifest and README and are shown under "Technical
details"; this file only says what the test is about, in everyday words.

Fields
------
name      short everyday title
group     rivers | floods2d | drainage | coupled | pipes | compat  (the filter chips on Tests & results)
question  the one question the test answers
what      what physically happens
why       why an engineer should care
must      what a good model must do (one line each)
"""

GROUPS = {
    "rivers": "Rivers and channels",
    "floods2d": "2D floods",
    "drainage": "Sewers and drainage",
    "coupled": "Sewers meeting streets",
    "pipes": "Water mains",
    "compat": "SWMM and EPANET compatibility",
}
GROUP_BLURBS = {
    "rivers": "One-dimensional flow along a channel: dam breaks, backwater, jumps and flow over a hump.",
    "floods2d": "Water spreading over ground: moving shorelines, floodplains, model cities and real dam failures.",
    "drainage": "Sewer pipes part full and surcharged, storage, pumps and backwater through manholes.",
    "coupled": "Water passing between the pipes and the street through manholes, both ways.",
    "pipes": "Pressurised networks: friction, loops, water hammer and pollutant transport.",
    "compat": "Does another engine give the same answers as EPA SWMM 5.2.4 or EPANET 2.2 on the same input?",
}

STORIES: dict[str, dict] = {
    # ── floods and channels (1D free surface) ────────────────────────────────
    "A1F-001": dict(
        name="Gentle backwater in a channel", group="rivers",
        question="Does the model get the water level right along a calm river reach?",
        what="Water flows slowly down a 1 km channel whose bed has been shaped so that the exact water surface is known everywhere. The level at the outlet backs water up the reach.",
        why="Most flood studies are steady backwater runs like this one. If the friction and slope balance is off, every flood level along the river is off too.",
        must=["keep the average depth error under 1 cm", "neither lose nor create water", "get steadily more accurate on finer grids"],
    ),
    "A1F-010": dict(
        name="Dam break onto dry ground", group="rivers",
        question="How far, and how fast, does the flood travel?",
        what="A 1-metre wall of water is released onto a dry, flat channel. It collapses into a wave whose front races over the dry ground at up to 6 m/s, thinning to a film at the tip, while a dip travels back into the reservoir.",
        why="Flood maps, evacuation times and dam-failure studies all depend on when water reaches dry land. A model that gets the front wrong gets the warning time wrong.",
        must=["put the flood front within 2.5 m of the exact one after 60 s", "neither lose nor create water", "get steadily more accurate on finer grids"],
    ),
    "A1F-011": dict(
        name="Dam break into shallow water", group="rivers",
        question="Does the model form the right bore when a flood runs into standing water?",
        what="A 1-metre reservoir is released into a channel already holding 10 cm of water. A steep bore (a moving step in the water surface) runs downstream while a smooth dip runs back upstream.",
        why="Real floods rarely meet bone-dry ground. The height and speed of the bore decide how hard the flood hits whatever is downstream.",
        must=["keep the average depth error under 5 cm after 30 s", "neither lose nor create water", "get steadily more accurate on finer grids"],
    ),
    "A1F-020": dict(
        name="Standing hydraulic jump", group="rivers",
        question="Does the model hold a hydraulic jump in the right place, at the right height?",
        what="Fast, shallow water (20 cm deep) meets slow, deep water (61 cm) and jumps abruptly between the two. With these exact depths the jump stands still at 50 m.",
        why="Jumps form below weirs, spillways and culverts, where they decide scour and the size of energy dissipators. A jump that drifts means the wrong design.",
        must=["match the depth profile within 1 %", "keep the jump where it should be (no drift)", "get steadily more accurate on finer grids"],
    ),
    "A1F-030": dict(
        name="Two channels meeting at a right angle", group="rivers",
        question="Does the model get water levels right where two channels join?",
        what="A side channel joins a main channel at 90° in a laboratory flume; depths and velocities were measured around the junction.",
        why="Confluences in rivers and sewers create backwater and losses that 1D models have to represent with simple rules.",
        must=["match the measured depths at the junction", "get the peak depth within 5 %"],
    ),
    "A1F-040": dict(
        name="Calm flow over a hump", group="rivers",
        question="Does the model get the dip in the water surface over a bump in the bed right?",
        what="Water flows steadily and calmly along a 25 m channel over a smooth 20 cm hump. The surface dips over the hump by an amount fixed exactly by conservation of flow and energy.",
        why="Weirs, sills, bridge piers and bed forms all change the water level this way. A model that gets the dip wrong gets every structure's backwater wrong.",
        must=["keep the average depth error under 5 mm", "carry the same flow along the whole channel", "get steadily more accurate on finer grids"],
    ),
    "A1F-041": dict(
        name="Flow speeding up over a hump", group="rivers",
        question="Does the model switch from calm to rapid flow at the right place?",
        what="With less water, the flow over the hump passes through critical depth at its top and races down the far side as fast, shallow flow, with no jump.",
        why="Control sections like this set water levels upstream of weirs and steep reaches. The switch to rapid flow is where many schemes struggle.",
        must=["keep the average depth error under 5 mm", "carry the same flow along the whole channel", "get steadily more accurate on finer grids"],
    ),
    "A1F-042": dict(
        name="Hump with a hydraulic jump", group="rivers",
        question="Does the jump below the hump stand in the right place?",
        what="A small flow goes rapid over the hump and then jumps back to calm, deeper water partway down its far side, at a point fixed exactly by the balance of momentum.",
        why="Jumps below weirs and sills decide where the bed scours and how big the protection must be.",
        must=["keep the average depth error under 5 mm", "carry the same flow along the whole channel", "get steadily more accurate on finer grids"],
    ),
    "A1F-043": dict(
        name="Still lake around an island", group="rivers",
        question="Does still water stay still over uneven, partly dry ground?",
        what="A lake 10 cm deep surrounds a 20 cm hump whose top stands out of the water. Nothing should move, ever.",
        why="Real terrain is uneven and partly dry. A model that cannot hold still water still invents currents everywhere, and they swamp the real ones.",
        must=["keep every velocity under 1 mm/s", "keep the water where it is (average depth change under 0.5 mm)"],
    ),
    "A1F-100": dict(
        name="Real sewer network, Odense", group="drainage",
        question="Does a sewer model reproduce ten years of measured water levels?",
        what="The Bellinge combined sewer system in Denmark has a published SWMM model and years of level, flow and pump records.",
        why="Field data is the final test of a drainage model: real rainfall, real pipes, real measurements.",
        must=["track the measured levels at 13 meters", "get the peak levels within 15 %"],
    ),
    # ── pipes and networks ───────────────────────────────────────────────────
    "A1P-001": dict(
        name="Friction loss in a pipe", group="pipes",
        question="Does the model lose the right amount of pressure to friction?",
        what="Water flows at 1 m/s through a 1 km, 300 mm pipe. Friction takes about 3.1 m of head, an amount fixed exactly by the Colebrook–White formula.",
        why="Every pipe in a water network loses head this way. Get the friction law wrong and pressures at customers' taps are wrong.",
        must=["get the head loss within 1 %", "keep heads along the pipe within 5 cm"],
    ),
    "A1P-010": dict(
        name="Looped water network", group="pipes",
        question="Does the model split flow correctly around loops in a network?",
        what="A small two-loop network fed by gravity. Water can reach each junction by more than one route, so flows and pressures must be solved together.",
        why="Real distribution networks are full of loops. This is the core calculation every network model performs.",
        must=["keep every junction head within 5 cm", "keep pipe flows within 0.1 %"],
    ),
    "A1P-020": dict(
        name="Water hammer: valve slammed shut", group="pipes",
        question="Is the pressure surge right when a valve shuts instantly?",
        what="Water moving at speed is stopped dead by a valve. The pressure jumps by the Joukowsky amount and the surge races back up the pipe at the speed of sound in water.",
        why="Surges burst pipes and damage pumps. Surge protection is sized from exactly this number.",
        must=["get the peak pressure within 2 %", "store exactly the water that kept flowing in", "converge at least at the rate a sharp front allows"],
    ),
    "A1P-021": dict(
        name="Slow valve closure with vapour cavities", group="pipes",
        question="Does the model capture cavities forming and collapsing in a pipe?",
        what="A laboratory pipe where closing a valve drops the pressure so low that the water column breaks; the cavity then collapses with a second surge.",
        why="Column separation causes the worst surges in real systems and is hard to model.",
        must=["get the peak pressure within 5 %", "time the cavity collapse within 0.05 s"],
    ),
    "A1P-030": dict(
        name="Pollutant spreading in a pipe", group="pipes",
        question="Does the model carry and spread a pollutant correctly?",
        what="A tracer is released continuously into steady flow. After an hour its front has moved 360 m and smeared out by dispersion, following an exact formula.",
        why="Contamination warnings, chlorine decay and sewer water quality all depend on getting both the travel and the spreading right.",
        must=["match the concentration profile within 2 %", "conserve the tracer within 0.5 %", "show second-order accuracy on finer grids"],
    ),
    # ── drainage networks (exact answers for link–node models) ───────────────
    "A1D-001": dict(
        name="Sewer pipes running part full", group="drainage",
        question="Does a drainage model get the depth right in a round pipe?",
        what="Three lines of 1 m sewer pipes, on a steady slope, carry three different flows that fill them to about a quarter, a half and three quarters. The depth in each pipe is fixed exactly by Manning's formula for a circle.",
        why="Pipe capacity checks, surcharge warnings and flood risk all start from the depth in a partly full pipe. This is the simplest thing a sewer model has to get right.",
        must=["keep every pipe and manhole depth within 1 cm", "pass the full inflow down every pipe"],
    ),
    "A1D-002": dict(
        name="Sewer pipes running full", group="drainage",
        question="When pipes surcharge, does the model get the water level in the manholes right?",
        what="Five pipes carry more water than they can as open channels, with the outlet held above the pipe tops, so they run full like water mains. The level in each manhole rises by an exact friction loss along each pipe.",
        why="Surcharged pipes push water up manholes and out onto streets. How high it rises decides whether a street floods.",
        must=["keep manhole levels within 1 cm", "pass the full inflow down every pipe"],
    ),
    "A1D-003": dict(
        name="Tank emptying through an outlet", group="drainage",
        question="Does a storage tank drain at the right rate?",
        what="A 2 m deep tank drains through an outlet whose flow grows with the square root of the depth. The depth after five minutes follows an exact formula.",
        why="Storage tanks and ponds are how drainage systems hold back floods. Their draining rate sets how much room is ready for the next storm.",
        must=["get the tank depth within 5 mm", "get the outlet flow within 5 L/s"],
    ),
    "A1D-004": dict(
        name="Pump working on its curve", group="drainage",
        question="Does the model run a pump at the right operating point?",
        what="A pump lifts water from a wet well into a rising main held at a fixed level. At steady state it must pass exactly the inflow, and its curve then fixes the water level in the well.",
        why="Pumping stations keep low-lying areas dry. A wrong operating point means the wrong wet-well level, the wrong switching and the wrong energy bill.",
        must=["get the wet-well level within 1 cm", "pump exactly the inflow"],
    ),
    "A1D-005": dict(
        name="Backwater up a sewer", group="drainage",
        question="Does a high water level at the outlet back up the right distance?",
        what="A kilometre of 1.2 m sewer drains to an outlet whose level is held high (as by a river in flood). Water backs up through twenty manholes, its depth falling gradually towards normal depth upstream, along an exactly integrated curve.",
        why="Outfalls into rivers and the sea are often submerged. How far the backwater reaches decides which basements and gullies flood.",
        must=["keep every manhole and pipe depth within 2 cm", "pass the full inflow down every pipe"],
    ),
    # ── 2D floods ────────────────────────────────────────────────────────────
    "A2A-001": dict(
        name="Water sloshing in a bowl", group="floods2d",
        question="Does the model move a shoreline back and forth correctly?",
        what="Water sloshes in a smooth bowl. The shoreline creeps up one side and retreats from the other, and the exact motion is known at every moment.",
        why="Flood edges wet and dry all the time. Models that mishandle the shoreline leak water or create it.",
        must=["keep the average depth error under 2 cm", "neither lose nor create water", "get steadily more accurate on finer grids"],
    ),
    "A2A-010": dict(
        name="Steady flow over a shaped bed", group="floods2d",
        question="Does a 2D model balance slope, pressure and friction like the 1D answer?",
        what="Steady flow down a 1 km × 100 m channel with a bed shaped so the exact depth is known. The run starts from a flat level and must settle to the right profile.",
        why="2D models are used for the same river reaches as 1D models; they must agree where the flow is effectively one-dimensional.",
        must=["keep the average depth error under 1 cm", "store the right volume of water", "get steadily more accurate on finer grids"],
    ),
    "A2A-020": dict(
        name="Supercritical flow turned by a wall", group="floods2d",
        question="Does the model put an angled shock wave in the right place?",
        what="Fast flow meets a wall angled at 15°. The water surface jumps along a straight line at 39.6° to the flow, and the depth almost doubles across it.",
        why="Shock waves form in steep channels, spillways and urban streets during flash floods; their angle sets where water overtops walls.",
        must=["keep the average depth error under 5 cm", "store the right volume of water", "get steadily more accurate on finer grids"],
    ),
    "A2F-001": dict(
        name="Malpasset dam failure, 1959", group="floods2d",
        question="Does a model reproduce a real dam-break disaster?",
        what="The Malpasset arch dam in France failed in 1959. The flood was reconstructed from high-water marks and power-line failure times.",
        why="Real dam-break studies must be checked against real events, not just exact solutions.",
        must=["match surveyed high-water marks within 15 %", "time the flood's arrival within 2 minutes"],
    ),
    "A2C-EA1": dict(
        name="Flooding a cut-off pond", group="floods2d",
        question="Does a pond behind a ridge fill and settle at the right level?",
        what="Rising water spills over a 10.25 m ridge into a hollow, then falls away again. The trapped pond must end level with the ridge crest.",
        why="Floodplains are full of hollows that fill and stay wet. Models must not lose or invent water as it is trapped.",
        must=["leave the pond at the crest level within 2 cm", "reach the right peak level"],
    ),
    "A2C-EA2": dict(
        name="Filling floodplain hollows", group="floods2d",
        question="Does every drop of inflow end up stored in the hollows?",
        what="A short flood spreads over a floodplain dotted with 16 shallow hollows and slowly fills them.",
        why="Slow, shallow filling is where models with poor wetting and drying lose water.",
        must=["store exactly the water let in (within 0.1 %)"],
    ),
    "A2C-EA4": dict(
        name="Flood spreading over a floodplain", group="floods2d",
        question="How fast does a breach flood spread over flat ground?",
        what="A levee-breach hydrograph pours onto a flat 1 km × 2 km floodplain and spreads out radially.",
        why="Breach studies estimate how fast water reaches homes. Speed and depth at the front set the hazard.",
        must=["store exactly the water let in (within 0.1 %)"],
    ),
    "A2C-EA5": dict(
        name="Valley flooding", group="floods2d",
        question="Does a dam-failure flood travel down a valley correctly?",
        what="A 3000 m³/s flood runs 17 km down a valley that starts steep and flattens out, switching between fast and slow flow.",
        why="Dam-break inundation maps cover exactly this kind of valley.",
        must=["store exactly the water let in (within 0.1 %)"],
    ),
    "A2L-010": dict(
        name="Dam break through a model city", group="floods2d",
        question="Does the model route a flood through streets correctly?",
        what="A laboratory dam break floods a grid of model buildings; depths were measured in the streets.",
        why="Urban flood models must handle buildings, street junctions and fast flow between them.",
        must=["match the gauge records", "place the flood front within 10 cm"],
    ),
    "A2L-011": dict(
        name="Flash flood in the Toce valley model", group="floods2d",
        question="Does the model reproduce a flash flood through a model town?",
        what="A scale model of the Toce valley with an urban district, flooded by a measured inflow.",
        why="Tests urban flooding against laboratory measurements.",
        must=["match the gauge records", "place the flood front within 10 cm"],
    ),
    "A2L-020": dict(
        name="Dam break over a sill", group="floods2d",
        question="Does the model handle a flood wave overtopping a hump and draining back?",
        what="A dam-break wave runs over a triangular sill, partly reflects, and leaves water trapped behind it.",
        why="Embankments and levees are overtopped exactly like this.",
        must=["match the gauge records", "place the flood front within 10 cm"],
    ),
    "A2L-EA6A": dict(
        name="Dam break past a building", group="floods2d",
        question="Does the model get the wake and jumps around a single building?",
        what="A laboratory dam break hits one block; a hydraulic jump forms in front of it and a wake behind.",
        why="Building-scale flood hazard needs the forces and depths around obstacles.",
        must=["match the gauge records", "time the front's arrival within 0.5 s"],
    ),
    "A12-001": dict(
        name="Sewer overflowing through a manhole", group="coupled",
        question="Does a coupled model exchange the right flow between sewer and street?",
        what="A laboratory rig where water surges up a manhole onto a surface and drains back.",
        why="Urban flooding happens where sewers and streets exchange water. The coupling equations are the weakest link of most models.",
        must=["match the measured exchange flow", "get the surface depth peak within 5 %"],
    ),
    "A12-010": dict(
        name="Manhole overflowing onto a street", group="coupled",
        question="Does a coupled model put all of the sewer's overflow onto the street?",
        what="A pipe delivers a steady flow to a manhole with no way out but up. It overflows onto a sloping street, and downstream the street carries the whole flow as a thin sheet whose depth is fixed exactly by the slope and roughness.",
        why="Surcharging manholes are where urban flooding starts. If the coupling loses or invents water here, every flood map built on it is wrong.",
        must=["release the full pipe flow onto the street", "get the street depth within 3 mm", "end with the water accounted for (0.5 %)"],
    ),
    "A12-011": dict(
        name="Flooded yard draining into a pipe", group="coupled",
        question="Does the flood drain down to the right level, and all of it out of the pipe?",
        what="A walled yard holds 30 cm of water that drains through a gully, raised 5 cm above the floor, into a pipe too small to take it all at once. The water above the gully's lip must leave through the pipe; the 5 cm below it must stay.",
        why="How quickly and how completely floodwater drains back into sewers decides how long streets stay flooded.",
        must=["leave the yard at the gully's lip (within 1 cm)", "send 225 m³ out of the pipe (within 2 %)", "end with the water accounted for (0.5 %)"],
    ),
    "A12-012": dict(
        name="Overflow and return", group="coupled",
        question="When a sewer overflows and then drains back, does every drop come out?",
        what="A storm overloads a sewer, which overflows into a hollow above a manhole. As the storm passes, the water runs back down the manhole and out of the system.",
        why="Water that surcharges onto streets usually returns to the sewer. A coupling that loses or gains water on the round trip gets flood volumes and outflows wrong.",
        must=["discharge all 180 m³ that came in (within 2 %)", "leave nothing on the surface", "end with the water accounted for (0.5 %)"],
    ),
    # ── compatibility ────────────────────────────────────────────────────────
    "B-EPANET-001": dict(
        name="Water distribution network", group="compat",
        question="Does an engine give the same answers as EPANET 2.2?",
        what="EPANET's own example network — junctions, a tank, a pump — run for 24 hours.",
        why="Utilities need to know an upgrade or a different engine will not change their results.",
        must=["match peak pressures within 1 % at every node", "match conveyed volumes within 1 % in every pipe"],
    ),
    "B-EXTRAN-001": dict(
        name="Sewer network routing", group="compat",
        question="Does an engine route a sewer network the same way as SWMM 5.2.4?",
        what="The classic EXTRAN example: a branching sewer with surcharge and three inflow hydrographs, routed for 8 hours.",
        why="SWMM results are used for permits and designs; a different engine must reproduce them.",
        must=["match peak depths within 1 % at every node", "match conveyed volumes within 1 % in every pipe"],
    ),
    "B-RTC-001": dict(
        name="Pump station switched by rules", group="compat",
        question="Do pumps switch on and off at the same moments as in SWMM 5.2.4?",
        what="A 90-node sewer with two pump stations whose pumps are switched by control rules on wet-well level; one pump switches 74 times in 36 hours.",
        why="Control rules decide overflows and energy use; a rule evaluated at a different moment changes both.",
        must=["match peak depths within 2 % at every node", "match pumped volumes within 2 %", "switch pumps within two minutes of SWMM"],
    ),
}

# Criteria in plain words: metric -> (label, how to phrase the observed value)
CHECK_NAMES = {
    "volume_front_error": "Flood front",
    "continuity_error": "Water balance",
    "front_position_error": "Leading edge (1 mm deep)",
    "global_mass_error": "Water conserved",
    "L1": "Average error",
    "L2": "Typical error",
    "Linf": "Worst error",
    "relative_head_loss": "Head loss",
    "peak_error": "Peak",
    "storage_balance_error": "Water stored",
    "expected_state_error": "Final state",
    "relative_peak": "Peaks",
    "relative_volume": "Volumes",
    "timing_error": "Timing",
    "NSE": "Fit to measurements",
    "arrival_time_error": "Arrival time",
}

VAR_WORDS = {"h": "depth", "u": "velocity", "Q": "flow", "p": "pressure", "c": "concentration", "volume": "volume"}
