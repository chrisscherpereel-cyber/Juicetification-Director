"""
director_manifests.py — the parameter schema for each simulation.

This is the Director's single source of truth for (a) the configuration forms and
(b) the launch links it builds. Each app owns the same schema in its own repo
(`manifest.py`, added when the sims were wired to `juice_director.py`); the copies
here let the Director render forms and encode configs without a live round-trip to
each app. Keep them in sync — when an app's manifest changes, bump its
SCHEMA_VERSION here too.

A param spec: {type, default, [min], [max], [choices], group, label}.
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
            "target_fill_ml":  {"type": "float", "default": 300.0, "min": 100, "max": 1000, "group": "Process", "label": "Fill target (mL)"},
            "within_sigma":    {"type": "float", "default": 2.0, "min": 0.1, "max": 20, "group": "Process", "label": "Within-subgroup σ (mL)"},
            "spec_low":        {"type": "float", "default": 294.0, "group": "Process", "label": "Spec low (mL)"},
            "spec_high":       {"type": "float", "default": 306.0, "group": "Process", "label": "Spec high (mL)"},
            "subgroup_n":      {"type": "int", "default": 5, "choices": [2, 3, 4, 5, 6, 7], "group": "Sampling", "label": "Subgroup size n"},
            "n_baseline":      {"type": "int", "default": 24, "min": 10, "max": 60, "group": "Sampling", "label": "Baseline subgroups"},
            "p_inspect":       {"type": "int", "default": 200, "min": 50, "max": 1000, "group": "Sampling", "label": "Bottles inspected/shift"},
            "p_baseline_rate": {"type": "float", "default": 0.04, "min": 0.0, "max": 0.5, "group": "Quality", "label": "In-control fraction defective"},
            "cost_recall":     {"type": "int", "default": 12000, "min": 0, "group": "Economics", "label": "$ per missed signal (Type II)"},
            "cost_linestop":   {"type": "int", "default": 3500, "min": 0, "group": "Economics", "label": "$ per false alarm (Type I)"},
            "trend_len":       {"type": "int", "default": 5, "min": 3, "max": 9, "group": "Rules", "label": "Run length = a trend"},
            "completion_salt": {"type": "str", "default": "squeeze-control-2026", "group": "Admin", "label": "Completion-code secret"},
        },
    },
    # ---------------------------------------------------------------- TOC
    "toc": {
        "app_key": "toc", "name": "Capacity Crush", "schema_version": 1,
        "params": {
            "capacities":          {"type": "list", "default": [1, 1, 1, 1, 1, 1, 0, 0, 0], "group": "Line", "label": "Dice per station"},
            "sides":               {"type": "list", "default": [6, 6, 6, 6, 6, 6, 0, 0, 0], "group": "Line", "label": "Faces per station"},
            "starting_inventory":  {"type": "int", "default": 0, "min": 0, "group": "Line", "label": "Starting inventory"},
            "simulation_years":    {"type": "int", "default": 1, "min": 1, "max": 5, "group": "Line", "label": "Years to simulate"},
            "wip_limit_on":        {"type": "bool", "default": False, "group": "Line", "label": "Cap WIP per station"},
            "wip_cap":             {"type": "int", "default": 10, "min": 0, "max": 99999, "group": "Line", "label": "WIP cap when on"},
            "supply_reliability":  {"type": "int", "default": 100, "min": 0, "max": 100, "group": "Variability", "label": "Supplier reliability %"},
            "demand_variable":     {"type": "bool", "default": False, "group": "Variability", "label": "Variable demand"},
            "demand_dice":         {"type": "int", "default": 1, "min": 1, "max": 10, "group": "Variability", "label": "Demand dice"},
            "demand_faces":        {"type": "int", "default": 6, "min": 1, "max": 100, "group": "Variability", "label": "Demand faces"},
            "reorder_point_on":    {"type": "bool", "default": False, "group": "Inventory", "label": "Manual reorder point"},
            "reorder_point":       {"type": "int", "default": 40, "min": 0, "group": "Inventory", "label": "Reorder point"},
            "scrap_on":            {"type": "bool", "default": False, "group": "Quality", "label": "Enable scrap"},
            "scrap_pct":           {"type": "int", "default": 0, "min": 0, "max": 100, "group": "Quality", "label": "Scrap % per station"},
            "fin_revenue_per_unit":{"type": "float", "default": 3.00, "group": "Economics", "label": "Revenue per unit"},
            "fin_alloc_pct":       {"type": "int", "default": 33, "min": 0, "max": 100, "group": "Economics", "label": "Fixed-cost allocation %"},
            "fin_wip_holding":     {"type": "float", "default": 0.04, "group": "Economics", "label": "WIP holding $/unit/day"},
            "fin_rmc":             {"type": "float", "default": 0.55, "group": "Economics", "label": "Raw material $/unit"},
            "fin_order_cost":      {"type": "float", "default": 25.00, "group": "Economics", "label": "$ per order"},
            "fin_order_size":      {"type": "int", "default": 150, "min": 1, "group": "Economics", "label": "Order size"},
            "fin_raw_holding":     {"type": "float", "default": 0.04, "group": "Economics", "label": "Raw holding $/unit/day"},
        },
    },
    # ---------------------------------------------------------------- APP
    "app": {
        "app_key": "app", "name": "Aggregate Anxiety", "schema_version": 1,
        "params": {
            "beginning_inventory": {"type": "int", "default": 2400, "min": 0, "group": "Inventory", "label": "Beginning inventory"},
            "safety_stock":        {"type": "int", "default": 2400, "min": 0, "group": "Inventory", "label": "Safety stock"},
            "max_inventory":       {"type": "int", "default": 30000, "min": 0, "group": "Inventory", "label": "Max inventory"},
            "bottles_per_worker":  {"type": "int", "default": 1000, "min": 1, "group": "Capacity", "label": "Bottles/worker/month"},
            "bottles_per_hour":    {"type": "int", "default": 5, "min": 1, "group": "Capacity", "label": "Bottles/worker-hour"},
            "hours_per_day":       {"type": "int", "default": 8, "min": 1, "max": 24, "group": "Capacity", "label": "Hours/day"},
            "working_days":        {"type": "int", "default": 25, "min": 1, "max": 31, "group": "Capacity", "label": "Working days/month"},
            "starting_workforce":  {"type": "int", "default": 8, "min": 0, "group": "Capacity", "label": "Starting workforce"},
            "regular_labor_cost":  {"type": "int", "default": 3200, "min": 0, "group": "Costs", "label": "Regular labor $/worker/mo"},
            "hiring_cost":         {"type": "int", "default": 600, "min": 0, "group": "Costs", "label": "Hiring $/worker"},
            "layoff_cost":         {"type": "int", "default": 900, "min": 0, "group": "Costs", "label": "Layoff $/worker"},
            "holding_cost":        {"type": "float", "default": 0.25, "min": 0, "group": "Costs", "label": "Holding $/bottle/mo"},
            "backorder_cost":      {"type": "float", "default": 1.50, "min": 0, "group": "Costs", "label": "Backorder $/bottle/mo"},
            "overtime_pct":        {"type": "float", "default": 0.20, "min": 0, "max": 1, "group": "Costs", "label": "Overtime cap (fraction)"},
            "overtime_cost":       {"type": "float", "default": 4.50, "min": 0, "group": "Costs", "label": "Overtime $/bottle"},
            "subcontract_cost":    {"type": "float", "default": 5.25, "min": 0, "group": "Costs", "label": "Subcontract $/bottle"},
            "forecast_demand":     {"type": "list", "default": [], "group": "Demand", "label": "12-month demand (blank = random per student)"},
        },
    },
    # ---------------------------------------------------------------- LEAN
    "lean": {
        "app_key": "lean", "name": "The Lean Rush", "schema_version": 1,
        "params": {
            "slow_station_bias":     {"type": "list", "default": ["Blender", "Blender", "Fruit", "Finish"], "group": "Scenario", "label": "Bottleneck bias pool"},
            "slow_mult_range":       {"type": "list", "default": [1.25, 1.60], "group": "Scenario", "label": "Bottleneck slowdown range"},
            "demand_mix":            {"type": "list", "default": ["Light", "Normal", "Normal", "Slammed"], "group": "Scenario", "label": "Rush intensity pool"},
            "demand_mult_range":     {"type": "list", "default": [0.90, 1.15], "group": "Scenario", "label": "Demand multiplier range"},
            "patience_choices":      {"type": "list", "default": [120, 135, 150, 170, 190], "group": "Scenario", "label": "Customer patience (s)"},
            "defect_base_range":     {"type": "list", "default": [0.12, 0.20], "group": "Scenario", "label": "Baseline defect range"},
            "start_batch_choices":   {"type": "list", "default": [2, 3, 4], "group": "Scenario", "label": "Inherited batch sizes"},
            "start_premade_choices": {"type": "list", "default": [6, 8, 10, 12], "group": "Scenario", "label": "Inherited made-ahead pile"},
            "horizon_s":             {"type": "float", "default": 900.0, "min": 60, "group": "Rush", "label": "Rush length (s)"},
            "blend_setup":           {"type": "float", "default": 6.0, "min": 0, "group": "Rush", "label": "Blend setup (s)"},
            "handoff_time":          {"type": "float", "default": 2.0, "min": 0, "group": "Rush", "label": "Handoff time (s)"},
            "lean_target":           {"type": "int", "default": 70, "min": 0, "max": 100, "group": "Grading", "label": "Lean score to finish"},
            "profit_target":         {"type": "float", "default": 0.0, "group": "Grading", "label": "Profit required"},
        },
    },
    # ---------------------------------------------------------------- FCST
    "fcst": {
        "app_key": "fcst", "name": "Forecast Frenzy", "schema_version": 1,
        "params": {
            "price":                {"type": "float", "default": 6.00, "min": 0, "group": "Economics", "label": "Price per drink"},
            "var_cost":             {"type": "float", "default": 2.25, "min": 0, "group": "Economics", "label": "Variable cost per drink"},
            "fruit_prep_cost":      {"type": "float", "default": 1.10, "min": 0, "group": "Economics", "label": "Fruit prep cost"},
            "bottle_cost":          {"type": "float", "default": 1.60, "min": 0, "group": "Economics", "label": "Bottle cost"},
            "wage_per_hr":          {"type": "float", "default": 16.00, "min": 0, "group": "Economics", "label": "Wage per hour"},
            "shift_hours":          {"type": "int", "default": 8, "min": 1, "max": 24, "group": "Economics", "label": "Shift hours"},
            "service_per_emp":      {"type": "int", "default": 22, "min": 1, "group": "Economics", "label": "Customers/employee/hour"},
            "promo_cost":           {"type": "float", "default": 60.0, "min": 0, "group": "Events", "label": "Promo cost"},
            "promo_lift":           {"type": "float", "default": 0.15, "min": 0, "max": 1, "group": "Events", "label": "Promo demand lift"},
            "satisfaction_penalty": {"type": "float", "default": 0.75, "min": 0, "group": "Events", "label": "Stockout penalty"},
            "base_demand":          {"type": "int", "default": 320, "min": 1, "group": "Demand", "label": "Base daily demand"},
            "completion_salt":      {"type": "str", "default": "forecast-frenzy-2026", "group": "Admin", "label": "Completion-code secret"},
        },
    },
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
