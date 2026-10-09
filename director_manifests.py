"""
director_manifests.py — the parameter schema for each simulation.

This is the Director's single source of truth for (a) the configuration forms and
(b) the launch links it builds. Each app owns the same schema in its own repo
(`manifest.py`); the copies here let the Director render forms and encode configs
without a live round-trip to each app. Keep them in sync — when an app's manifest
changes, bump its SCHEMA_VERSION here too.

A param spec: {type, default, [min], [max], [choices], group, label, help}.
  • label — the field name the instructor sees.
  • help  — a plain-language definition plus how changing it affects students.
            Shown as the tooltip on each field, so the form needs no manual.
Types: int, float, bool, str, list (list is entered as comma-separated values).
"""

from __future__ import annotations

import base64
import json

MANIFESTS = {
    # ---------------------------------------------------------------- SPC
    "spc": {
        "app_key": "spc", "name": "Squeeze Control", "schema_version": 1,
        "params": {
            "target_fill_ml":  {"type": "float", "default": 300.0, "min": 100, "max": 1000, "group": "Process", "label": "Fill target (mL)",
                                "help": "The amount each bottle is meant to be filled to. Sets the center line of the students' X-bar chart. Mostly rescales the numbers; keep it between the spec limits."},
            "within_sigma":    {"type": "float", "default": 2.0, "min": 0.1, "max": 20, "group": "Process", "label": "Filler variation σ (mL)",
                                "help": "How much the filler naturally varies bottle-to-bottle. Higher = noisier charts and wider control limits, so real problems are harder to spot; lower = cleaner charts that are easier to read."},
            "spec_low":        {"type": "float", "default": 294.0, "group": "Process", "label": "Spec limit — low (mL)",
                                "help": "The lowest fill the customer will accept. A narrower spec (raise this) makes more bottles fail tolerance and the process look less capable."},
            "spec_high":       {"type": "float", "default": 306.0, "group": "Process", "label": "Spec limit — high (mL)",
                                "help": "The highest acceptable fill. A narrower spec (lower this) makes capability look worse and pushes students to reduce variation."},
            "subgroup_n":      {"type": "int", "default": 5, "choices": [2, 3, 4, 5, 6, 7], "group": "Sampling", "label": "Sample size per subgroup (n)",
                                "help": "How many bottles are measured in each sample. Larger n tightens the X-bar limits and catches smaller mean shifts (harder, more rigorous); smaller n is looser and less sensitive."},
            "n_baseline":      {"type": "int", "default": 24, "min": 10, "max": 60, "group": "Sampling", "label": "Baseline subgroups",
                                "help": "How many stable samples are used to set the control limits. More gives steadier, more trustworthy limits but a longer setup phase; fewer is quicker but shakier."},
            "p_inspect":       {"type": "int", "default": 200, "min": 50, "max": 1000, "group": "Sampling", "label": "Bottles inspected per shift",
                                "help": "Sample size for the defect (p) chart. More inspected = tighter, more sensitive defect limits; fewer = a noisier p-chart that reacts to chance."},
            "p_baseline_rate": {"type": "float", "default": 0.04, "min": 0.0, "max": 0.5, "group": "Quality", "label": "Normal defect rate",
                                "help": "The fraction defective when the line is healthy (0.04 = 4%). Sets how 'bad' the stable process is and where the p-chart center line sits. Higher makes defects routine."},
            "cost_recall":     {"type": "int", "default": 12000, "min": 0, "group": "Economics", "label": "Cost of a missed signal ($)",
                                "help": "Penalty when a student ignores a real out-of-control signal and ships bad product. Raise it to make under-reacting very costly, pushing students to act on signals."},
            "cost_linestop":   {"type": "int", "default": 3500, "min": 0, "group": "Economics", "label": "Cost of a false alarm ($)",
                                "help": "Penalty when a student stops a healthy line over normal noise. Raise it to punish over-reacting, tuning the tension between catching problems and crying wolf."},
            "trend_len":       {"type": "int", "default": 5, "min": 3, "max": 9, "group": "Rules", "label": "Points in a row = a trend",
                                "help": "How many steadily rising/falling points count as a trend signal. Fewer = more sensitive (more signals and more false alarms); more = fewer signals."},
            "completion_salt": {"type": "str", "default": "squeeze-control-2026", "group": "Admin", "label": "Completion-code secret",
                                "help": "A private phrase used to make each student's completion code. No effect on gameplay — change it per class so a code from one section can't be reused in another."},
        },
    },
    # ---------------------------------------------------------------- TOC
    "toc": {
        "app_key": "toc", "name": "Capacity Crush", "schema_version": 1,
        "params": {
            "capacities":          {"type": "list", "default": [1, 1, 1, 1, 1, 1, 0, 0, 0], "group": "Line", "label": "Machines per station (9 values)",
                                    "help": "How many dice (machines) sit at each of the 9 stations; 0 turns a station off. Unbalancing these creates a clear bottleneck for students to find; the default is a balanced 6-station line."},
            "sides":               {"type": "list", "default": [6, 6, 6, 6, 6, 6, 0, 0, 0], "group": "Line", "label": "Die faces per station (9 values)",
                                    "help": "The faces on each station's die — its output range each hour. More faces = higher average output but more variability, so students see how variability starves or floods neighboring stations."},
            "starting_inventory":  {"type": "int", "default": 0, "min": 0, "group": "Line", "label": "Starting work-in-process",
                                    "help": "Units already in the line when the run begins. More acts as a buffer that hides early starvation and speeds the ramp-up; 0 shows a stark cold start."},
            "simulation_years":    {"type": "int", "default": 1, "min": 1, "max": 5, "group": "Line", "label": "Years to simulate",
                                    "help": "How long the run lasts. Longer runs average out luck and show steady-state behavior; shorter runs are noisier and more variable."},
            "wip_limit_on":        {"type": "bool", "default": False, "group": "Line", "label": "Cap work-in-process (pull system)",
                                    "help": "Turns the push line into a pull/CONWIP line. On, it demonstrates that limiting inventory cuts lead time without losing throughput — a core lesson."},
            "wip_cap":             {"type": "int", "default": 10, "min": 0, "max": 99999, "group": "Line", "label": "WIP cap per station",
                                    "help": "The inventory limit at each station when the cap is on. Lower squeezes inventory harder (shorter lead times but more blocking); only used when the cap is enabled."},
            "supply_reliability":  {"type": "int", "default": 100, "min": 0, "max": 100, "group": "Variability", "label": "Supplier reliability (%)",
                                    "help": "How often raw material actually arrives. Below 100 starves the first station and cuts throughput, teaching supply variability; 100 means the line is never starved."},
            "demand_variable":     {"type": "bool", "default": False, "group": "Variability", "label": "Variable customer demand",
                                    "help": "On, demand fluctuates instead of being steady, so unsold units pile up as finished goods and shortages appear — teaches demand variability."},
            "demand_dice":         {"type": "int", "default": 1, "min": 1, "max": 10, "group": "Variability", "label": "Demand dice",
                                    "help": "How many dice are rolled for demand each hour. More dice raise and smooth average demand; combined with faces, they set how bumpy the market is."},
            "demand_faces":        {"type": "int", "default": 6, "min": 1, "max": 100, "group": "Variability", "label": "Demand die faces",
                                    "help": "Faces on the demand die. More faces = higher, more variable demand. The default (1×6) roughly matches one station's output."},
            "reorder_point_on":    {"type": "bool", "default": False, "group": "Inventory", "label": "Manual reorder point",
                                    "help": "Lets students set when to reorder raw material instead of using the automatic trigger. On, it turns the run into a safety-stock exercise."},
            "reorder_point":       {"type": "int", "default": 40, "min": 0, "group": "Inventory", "label": "Reorder point",
                                    "help": "Raw-material level that triggers a new order (when manual reordering is on). Higher holds more safety stock — less starvation but more holding cost."},
            "scrap_on":            {"type": "bool", "default": False, "group": "Quality", "label": "Enable scrap / defects",
                                    "help": "On, some units are scrapped, so quality eats into capacity — students learn that yield loss at a bottleneck is especially expensive."},
            "scrap_pct":           {"type": "int", "default": 0, "min": 0, "max": 100, "group": "Quality", "label": "Scrap rate per station (%)",
                                    "help": "Percent of units lost to defects at each station (when scrap is on). Higher yield loss lowers throughput and sharpens the quality-as-capacity lesson."},
            "fin_revenue_per_unit":{"type": "float", "default": 3.00, "group": "Economics", "label": "Revenue per unit ($)",
                                    "help": "Price earned per finished bottle. Raises or lowers how profitable throughput is; the whole P&L scales with this."},
            "fin_alloc_pct":       {"type": "int", "default": 33, "min": 0, "max": 100, "group": "Economics", "label": "Fixed-cost allocation (%)",
                                    "help": "Share of machine (die) fixed cost charged each period. Higher makes expensive high-capacity dice look worse, sharpening the 'bigger isn't always better' point."},
            "fin_wip_holding":     {"type": "float", "default": 0.04, "group": "Economics", "label": "WIP holding cost ($/unit/day)",
                                    "help": "Daily cost to hold each in-process unit. Higher punishes piling up inventory, rewarding pull systems and low WIP."},
            "fin_rmc":             {"type": "float", "default": 0.55, "group": "Economics", "label": "Raw material cost ($/unit)",
                                    "help": "Cost of each unit of raw material. Higher squeezes margin and makes scrap and overordering hurt more."},
            "fin_order_cost":      {"type": "float", "default": 25.00, "group": "Economics", "label": "Cost per order ($)",
                                    "help": "Fixed cost each time raw material is ordered. Higher pushes the best order size (EOQ) up — central to the inventory labs."},
            "fin_order_size":      {"type": "int", "default": 150, "min": 1, "group": "Economics", "label": "Order size (units)",
                                    "help": "How much raw material is bought per order. Interacts with order and holding costs to show the EOQ tradeoff."},
            "fin_raw_holding":     {"type": "float", "default": 0.04, "group": "Economics", "label": "Raw holding cost ($/unit/day)",
                                    "help": "Daily cost to hold raw material. Higher makes large orders/safety stock expensive, part of the EOQ and safety-stock math."},
        },
    },
    # ---------------------------------------------------------------- APP
    "app": {
        "app_key": "app", "name": "Aggregate Anxiety", "schema_version": 1,
        "params": {
            "beginning_inventory": {"type": "int", "default": 2400, "min": 0, "group": "Inventory", "label": "Beginning inventory (bottles)",
                                    "help": "Finished bottles on hand before the plan starts. More reduces how much must be produced early; it feeds directly into the level-plan math."},
            "safety_stock":        {"type": "int", "default": 2400, "min": 0, "group": "Inventory", "label": "Safety stock target (bottles)",
                                    "help": "The ending buffer a plan aims to keep. Higher forces extra production and inventory (more holding cost), shifting the chase-vs-level tradeoff."},
            "max_inventory":       {"type": "int", "default": 30000, "min": 0, "group": "Inventory", "label": "Maximum inventory (bottles)",
                                    "help": "A ceiling on finished goods. Lowering it constrains level plans and can force a chase strategy; rarely binding at the default."},
            "bottles_per_worker":  {"type": "int", "default": 1000, "min": 1, "group": "Capacity", "label": "Output per worker per month",
                                    "help": "How much one worker produces monthly. Higher means fewer workers are needed, lowering labor cost and changing hire/layoff sizes."},
            "bottles_per_hour":    {"type": "int", "default": 5, "min": 1, "group": "Capacity", "label": "Bottles per worker-hour",
                                    "help": "A building block of worker capacity (× hours × days). Raising it increases each worker's monthly output."},
            "hours_per_day":       {"type": "int", "default": 8, "min": 1, "max": 24, "group": "Capacity", "label": "Hours per day",
                                    "help": "Shift length. Part of the per-worker capacity calculation; longer shifts mean more output per worker."},
            "working_days":        {"type": "int", "default": 25, "min": 1, "max": 31, "group": "Capacity", "label": "Working days per month",
                                    "help": "Producing days each month. More days increase monthly capacity per worker."},
            "starting_workforce":  {"type": "int", "default": 8, "min": 0, "group": "Capacity", "label": "Starting workforce",
                                    "help": "Workers on payroll before January. More starting workers means fewer hires (or more layoffs) in the plan, changing which strategy is cheapest."},
            "regular_labor_cost":  {"type": "int", "default": 3200, "min": 0, "group": "Costs", "label": "Regular labor ($/worker/month)",
                                    "help": "Monthly pay per worker — usually the biggest cost. Higher makes workforce decisions matter more and level plans pricier."},
            "hiring_cost":         {"type": "int", "default": 600, "min": 0, "group": "Costs", "label": "Hiring cost ($/worker)",
                                    "help": "One-time cost to add a worker. Higher makes chase plans (which hire and fire to track demand) more expensive versus a steady level plan."},
            "layoff_cost":         {"type": "int", "default": 900, "min": 0, "group": "Costs", "label": "Layoff cost ($/worker)",
                                    "help": "One-time cost to cut a worker. Higher penalizes shrinking the workforce, again favoring level over chase."},
            "holding_cost":        {"type": "float", "default": 0.25, "min": 0, "group": "Costs", "label": "Holding cost ($/bottle/month)",
                                    "help": "Cost to carry a bottle for a month. Higher punishes building inventory ahead, tilting students toward a chase plan — the core tradeoff."},
            "backorder_cost":      {"type": "float", "default": 1.50, "min": 0, "group": "Costs", "label": "Backorder cost ($/bottle/month)",
                                    "help": "Penalty per bottle of unmet demand. Higher punishes shortages, pushing students to build ahead or level-produce."},
            "overtime_pct":        {"type": "float", "default": 0.20, "min": 0, "max": 1, "group": "Costs", "label": "Overtime limit (fraction)",
                                    "help": "How much above regular output overtime can add (0.20 = 20%). More overtime gives students a flexible way to meet peaks without hiring."},
            "overtime_cost":       {"type": "float", "default": 4.50, "min": 0, "group": "Costs", "label": "Overtime cost ($/bottle)",
                                    "help": "Cost of each overtime bottle. Cheaper overtime makes it an attractive alternative to hiring; pricier pushes other strategies."},
            "subcontract_cost":    {"type": "float", "default": 5.25, "min": 0, "group": "Costs", "label": "Subcontract cost ($/bottle)",
                                    "help": "Cost to buy a bottle from outside. Lower makes outsourcing peaks appealing; higher forces in-house solutions."},
            "forecast_demand":     {"type": "list", "default": [], "group": "Demand", "label": "12-month demand (leave blank for random)",
                                    "help": "Enter 12 monthly demand numbers to give everyone the same seasonal curve, or leave blank so each student gets a unique random demand pattern."},
        },
    },
    # ---------------------------------------------------------------- LEAN
    "lean": {
        "app_key": "lean", "name": "The Lean Rush", "schema_version": 1,
        "params": {
            "slow_station_bias":     {"type": "list", "default": ["Blender", "Blender", "Fruit", "Finish"], "group": "Scenario", "label": "Likely bottleneck stations",
                                      "help": "The pool the slow station is drawn from (repeats weight it). Loading it toward one station makes that the usual constraint students must diagnose."},
            "slow_mult_range":       {"type": "list", "default": [1.25, 1.60], "group": "Scenario", "label": "Bottleneck slowdown range (min, max)",
                                      "help": "How much slower the bottleneck runs than normal. Higher values make a more punishing constraint, so ignoring it costs more."},
            "demand_mix":            {"type": "list", "default": ["Light", "Normal", "Normal", "Slammed"], "group": "Scenario", "label": "Rush intensity mix",
                                      "help": "The pool of how busy the morning rush is. More 'Slammed' entries mean busier, higher-pressure rushes where waste is more visible."},
            "demand_mult_range":     {"type": "list", "default": [0.90, 1.15], "group": "Scenario", "label": "Demand multiplier range (min, max)",
                                      "help": "A random band applied to demand. Wider = more variation between students' shops; narrower = more uniform."},
            "patience_choices":      {"type": "list", "default": [120, 135, 150, 170, 190], "group": "Scenario", "label": "Customer patience (seconds)",
                                      "help": "How long customers wait before walking out. Lower values make customers leave sooner, punishing long queues and lead times."},
            "defect_base_range":     {"type": "list", "default": [0.12, 0.20], "group": "Scenario", "label": "Baseline defect rate (min, max)",
                                      "help": "How error-prone the crew starts. Higher means more rework and waste, so quality improvements pay off more."},
            "start_batch_choices":   {"type": "list", "default": [2, 3, 4], "group": "Scenario", "label": "Inherited batch size",
                                      "help": "How many drinks the previous shift blended at once. Bigger starting batches give students more over-batching to discover and fix."},
            "start_premade_choices": {"type": "list", "default": [6, 8, 10, 12], "group": "Scenario", "label": "Inherited made-ahead cups",
                                      "help": "How many cups were made before the rush. More pre-made means more overproduction/waste to notice and eliminate."},
            "horizon_s":             {"type": "float", "default": 900.0, "min": 60, "group": "Rush", "label": "Rush length (seconds)",
                                      "help": "How long the timed rush runs (900 = 15 min). Longer rushes produce steadier results; shorter ones are more variable."},
            "blend_setup":           {"type": "float", "default": 6.0, "min": 0, "group": "Rush", "label": "Blend setup time (seconds)",
                                      "help": "Seconds lost setting up each blend. Higher setup makes batching tempting but rewards fixing flow — it's the heart of the batch-size lesson."},
            "handoff_time":          {"type": "float", "default": 2.0, "min": 0, "group": "Rush", "label": "Handoff time (seconds)",
                                      "help": "Time lost passing an order between specialists. Higher penalizes over-dividing the work into handoffs."},
            "lean_target":           {"type": "int", "default": 70, "min": 0, "max": 100, "group": "Grading", "label": "Lean score to finish",
                                      "help": "The score students must reach to complete the lab. Higher sets a stricter bar that demands more improvement."},
            "profit_target":         {"type": "float", "default": 0.0, "group": "Grading", "label": "Profit required to pass ($)",
                                      "help": "Minimum profit to finish. Above 0 forces students to be profitable as well as lean, not just efficient."},
        },
    },
    # ---------------------------------------------------------------- FCST
    "fcst": {
        "app_key": "fcst", "name": "Forecast Frenzy", "schema_version": 1,
        "params": {
            "price":                {"type": "float", "default": 6.00, "min": 0, "group": "Economics", "label": "Price per drink ($)",
                                     "help": "What a drink sells for. Higher prices make a stockout (a lost sale) more costly, pushing students to stock and staff for demand."},
            "var_cost":             {"type": "float", "default": 2.25, "min": 0, "group": "Economics", "label": "Variable cost per drink ($)",
                                     "help": "Cost to make one drink. Together with price it sets the profit margin, which drives the overstock-vs-understock tradeoff students face."},
            "fruit_prep_cost":      {"type": "float", "default": 1.10, "min": 0, "group": "Economics", "label": "Fruit prep cost ($)",
                                     "help": "Part of the cost of each drink. Raising it increases the cost of over-preparing, so bad forecasts hurt more."},
            "bottle_cost":          {"type": "float", "default": 1.60, "min": 0, "group": "Economics", "label": "Bottle cost ($)",
                                     "help": "Another per-drink cost component. Higher makes leftover/unsold stock more expensive."},
            "wage_per_hr":          {"type": "float", "default": 16.00, "min": 0, "group": "Economics", "label": "Wage per hour ($)",
                                     "help": "Staff pay. Higher wages make overstaffing costly, so accurate demand forecasts matter more for the staffing decision."},
            "shift_hours":          {"type": "int", "default": 8, "min": 1, "max": 24, "group": "Economics", "label": "Shift length (hours)",
                                     "help": "How long staff work. Sets each employee's daily capacity and total labor cost."},
            "service_per_emp":      {"type": "int", "default": 22, "min": 1, "group": "Economics", "label": "Customers served per employee per hour",
                                     "help": "How many customers one employee can serve hourly. Lower means more staff are needed for the same demand, raising the stakes of the forecast."},
            "promo_cost":           {"type": "float", "default": 60.0, "min": 0, "group": "Events", "label": "Promotion cost ($)",
                                     "help": "What running a promotion costs. Higher makes a promo pay off only when it clearly lifts demand."},
            "promo_lift":           {"type": "float", "default": 0.15, "min": 0, "max": 1, "group": "Events", "label": "Promotion demand lift (fraction)",
                                     "help": "How much a promotion raises demand (0.15 = 15%). Higher makes promotions more attractive and worth forecasting around."},
            "satisfaction_penalty": {"type": "float", "default": 0.75, "min": 0, "group": "Events", "label": "Stockout penalty ($)",
                                     "help": "The hit for failing to serve a customer. Higher punishes under-forecasting, pushing students to stock and staff more generously."},
            "base_demand":          {"type": "int", "default": 320, "min": 1, "group": "Demand", "label": "Baseline daily demand",
                                     "help": "The typical number of customers a day. Scales the whole scenario — higher means a busier bar with larger staffing and stocking numbers."},
            "completion_salt":      {"type": "str", "default": "forecast-frenzy-2026", "group": "Admin", "label": "Completion-code secret",
                                     "help": "A private phrase used to make each student's completion code. No effect on gameplay — change it per class so codes can't be reused across sections."},
        },
    },
}


# ---------------------------------------------------------------- TOC V3
# Capacity Crush V3 is the same simulation and the same parameter schema as "toc", plus the run
# length V3 added. Derived from the "toc" entry rather than copied so the shared 21 parameters
# cannot drift between the two catalog entries.
def _toc3_params():
    out = {}
    for key, spec in MANIFESTS["toc"]["params"].items():
        out[key] = spec
        if key == "simulation_years":          # keep run length next to the other timing control
            out["horizon"] = {
                "type": "str", "default": "Full year",
                "choices": ["One shift (8 h)", "One week (40 h)", "Six weeks (240 h)", "Full year"],
                "group": "Line", "label": "Run length",
                "help": "How long each run lasts. A full year averages the dice out and shows the "
                        "line's steady rate; a shift or a week shows the swings a real shop floor "
                        "lives with. Challenges are always judged over a full year regardless of "
                        "this setting, so a short run can never decide a pass.",
            }
    return out


MANIFESTS["toc3"] = {
    **MANIFESTS["toc"],
    "app_key": "toc3",
    "name": "Capacity Crush V3",
    "params": _toc3_params(),
}


def get_manifest(app_key):
    return MANIFESTS.get(app_key)


def groups(manifest):
    """Ordered list of group names, preserving first-seen order."""
    out = []
    for spec in manifest["params"].values():
        g = spec.get("group", "General")
        if g not in out:
            out.append(g)
    return out


def defaults(manifest):
    return {k: s["default"] for k, s in manifest["params"].items()}


def _coerce(spec, value):
    t = spec.get("type")
    try:
        if t == "int":
            value = int(value)
        elif t == "float":
            value = float(value)
        elif t == "bool":
            value = bool(value)
        elif t == "list":
            value = list(value)
    except (TypeError, ValueError):
        return spec["default"]
    if t in ("int", "float"):
        if "min" in spec and value < spec["min"]:
            value = spec["min"]
        if "max" in spec and value > spec["max"]:
            value = spec["max"]
    if "choices" in spec and value not in spec["choices"]:
        return spec["default"]
    return value


def validate_params(manifest, raw):
    """Return a full param dict: defaults overridden by validated `raw` values."""
    out = defaults(manifest)
    for k, v in (raw or {}).items():
        if k in manifest["params"]:
            out[k] = _coerce(manifest["params"][k], v)
    return out


def _fmt_value(v):
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, list):
        return "random" if not v else ", ".join(str(x) for x in v)
    return str(v)


def changed_from_default(manifest, params):
    """List of (label, value, default) for params that differ from their default."""
    out = []
    for k, s in manifest["params"].items():
        d = s["default"]
        v = params.get(k, d)
        if v != d:
            out.append((s["label"], v, d))
    return out


def summarize_changes(manifest, params, max_items=8):
    """One-line, human-readable summary of what a config changed from defaults."""
    ch = changed_from_default(manifest, params)
    if not ch:
        return "All settings at their defaults."
    parts = [f"{label} → {_fmt_value(v)}" for label, v, _d in ch[:max_items]]
    s = "; ".join(parts)
    extra = len(ch) - max_items
    if extra > 0:
        s += f"; +{extra} more"
    return s


def parse_list_text(text, element_type=float):
    """Parse a comma-separated string into a typed list. Blank → []."""
    text = (text or "").strip()
    if not text:
        return []
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if element_type is float:
            try:
                out.append(int(part) if part.lstrip("-").isdigit() else float(part))
            except ValueError:
                out.append(part)  # keep strings (e.g. station names)
        else:
            out.append(part)
    return out


def list_to_text(value):
    if not isinstance(value, (list, tuple)):
        return ""
    return ", ".join(str(v) for v in value)


def encode_cfg(params) -> str:
    """Base64-url JSON, matching juice_director.encode_cfg in the sims."""
    return base64.urlsafe_b64encode(
        json.dumps(params, separators=(",", ":")).encode()).decode()


def decode_cfg(token) -> dict:
    return json.loads(base64.urlsafe_b64decode(token.encode()).decode())
