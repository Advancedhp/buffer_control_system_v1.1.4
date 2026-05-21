"""Schema definitions for the buffer control system."""

REQUIRED_COLUMNS = [
    "item_id",
    "item_name",
    "unit",
    "period",
    "rop_name",
    "criticality_class",
    "O",
    "P",
    "R",
    "D_avg",
    "sigma_D",
    "L_avg",
    "sigma_L",
    "rop_load",
    "planned_flow",
    "actual_flow",
    "p_diag",
    "p_rep",
    "h",
    "Cstop",
    "z0",
    "alpha",
    "beta",
    "Kcrit_manual",
    "Kload_manual",
    "Kdev_manual",
    "coeff_mode",
]

NUMERIC_COLUMNS = [
    "O", "P", "R", "D_avg", "sigma_D", "L_avg", "sigma_L",
    "rop_load", "planned_flow", "actual_flow", "p_diag", "p_rep",
    "h", "Cstop", "z0", "alpha", "beta", "Kcrit_manual",
    "Kload_manual", "Kdev_manual",
]

TEXT_COLUMNS = [
    "item_id", "item_name", "unit", "period", "rop_name",
    "criticality_class", "coeff_mode",
]

OUTPUT_COLUMNS = [
    "A", "sigma_LT", "z", "Kcrit", "Kload", "Kdev", "Bstat",
    "Btar", "Pshort", "Pshort_current", "holding_cost", "expected_stop_loss",
    "expected_total_cost", "Bopt", "reorder_point", "Ibuf", "status",
    "optimization_note", "recommendation",
]

CRITICALITY_CLASSES = ["обычная", "важная", "критичная", "блокирующая"]
COEFF_MODES = ["auto", "manual"]

STATUS_ORDER = [
    "Критическое отклонение",
    "Предупреждение",
    "Норма",
    "Избыточный буфер",
]
