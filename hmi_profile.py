def get_hmi_profile(range_nm):

    if range_nm <= 20:
        return {
            "target_symbol": 6,
            "trail_points": 20,
            "predictor_minutes": 2.0,
            "fix_symbol": 4,
            "navaid_symbol": 4,
            "label_mode": "full",
            "show_fix_names": True,
            "show_navaid_names": True,
        }

    elif range_nm <= 40:
        return {
            "target_symbol": 5,
            "trail_points": 16,
            "predictor_minutes": 1.8,
            "fix_symbol": 3,
            "navaid_symbol": 3,
            "label_mode": "normal",
            "show_fix_names": True,
            "show_navaid_names": False,
        }

    elif range_nm <= 80:
        return {
            "target_symbol": 4,
            "trail_points": 12,
            "predictor_minutes": 1.5,
            "fix_symbol": 2,
            "navaid_symbol": 2,
            "label_mode": "minimal",
            "show_fix_names": False,
            "show_navaid_names": False,
        }

    else:
        return {
            "target_symbol": 3,
            "trail_points": 8,
            "predictor_minutes": 1.2,
            "fix_symbol": 2,
            "navaid_symbol": 2,
            "label_mode": "minimal",
            "show_fix_names": False,
            "show_navaid_names": False,
        }