from math import log1p


def progressive_log_alpha_ratio(ratio):
    ratio = max(0.0, min(1.0, float(ratio)))
    if ratio == 0.0 or ratio == 1.0:
        return ratio

    curve_strength = 9.0
    return 1 - (log1p(curve_strength * (1 - ratio)) / log1p(curve_strength))
