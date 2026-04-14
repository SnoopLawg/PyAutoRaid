"""
StatusEffectTypeId → sim debuff/buff name mapping.
From IL2CPP dump: SharedModel.Meta.Skills.StatusEffectTypeId enum.
"""

# StatusEffectTypeId → (sim_name, is_debuff_on_cb, is_buff_on_ally)
STATUS_EFFECT_MAP = {
    # CC (CB immune)
    10: ("stun", True, False),
    20: ("freeze", True, False),
    30: ("sleep", True, False),
    40: ("provoke", True, False),
    # Buffs on allies
    50: ("counterattack", False, True),
    60: ("block_damage", False, True),
    100: ("block_debuffs", False, True),
    110: ("block_buffs", True, False),
    120: ("atk_up_25", False, True),
    121: ("atk_up", False, True),       # ATK Up 50%
    130: ("dec_atk_25", True, False),
    131: ("dec_atk", True, False),       # Dec ATK 50%
    140: ("inc_def_30", False, True),
    141: ("inc_def", False, True),       # DEF Up 60%
    150: ("dec_def_30", True, False),
    151: ("def_down", True, False),      # DEF Down 60%
    160: ("inc_spd_15", False, True),
    161: ("inc_spd", False, True),       # Inc SPD 30%
    170: ("dec_spd_15", True, False),
    171: ("dec_spd", True, False),       # Dec SPD 30%
    220: ("inc_acc_25", False, True),
    221: ("inc_acc_50", False, True),
    240: ("inc_cr_15", False, True),
    241: ("inc_cr_30", False, True),
    260: ("inc_cd_15", False, True),
    261: ("inc_cd_30", False, True),
    270: ("dec_cd_15", True, False),
    271: ("dec_cd_25", True, False),
    # Debuffs on CB
    70: ("block_heal_100", True, False),
    71: ("block_heal_50", True, False),
    80: ("poison_5pct", True, False),    # Poison 5%
    81: ("poison_2pct", True, False),    # Poison 2.5%
    90: ("cont_heal", False, True),      # Continuous Heal 7.5%
    91: ("cont_heal_15", False, True),   # Continuous Heal 15%
    280: ("shield", False, True),
    300: ("revive_on_death", False, True),
    310: ("ally_protect", False, True),  # Ally Protect 50%
    311: ("ally_protect_25", False, True),
    320: ("unkillable", False, True),
    350: ("weaken", True, False),        # Weaken 25% (Increase Damage Taken)
    351: ("weaken_15", True, False),
    360: ("block_revive", True, False),
    410: ("reflect_15", False, True),
    411: ("reflect_30", False, True),
    460: ("leech", True, False),         # Life Drain on Damage 10%
    470: ("hp_burn", True, False),       # HP Burn
    480: ("invisible", False, True),
    490: ("fear", True, False),
    491: ("true_fear", True, False),
    500: ("poison_sensitivity", True, False),  # Increase Poisoning 25%
    501: ("poison_sensitivity_50", True, False),
    510: ("strengthen_15", False, True),
    511: ("strengthen", False, True),    # Reduce Damage Taken 25% = Strengthen
    710: ("inc_res_25", False, True),
    711: ("inc_res_50", False, True),
    720: ("dec_res_25", True, False),
    721: ("dec_res_50", True, False),
}

# Sim-relevant debuffs (placed on CB debuff bar)
CB_DEBUFFS = {
    "poison_5pct", "poison_2pct", "hp_burn", "def_down", "dec_def_30",
    "weaken", "weaken_15", "dec_atk", "dec_atk_25", "leech",
    "poison_sensitivity", "poison_sensitivity_50",
    "dec_spd", "dec_spd_15", "block_heal_100", "block_heal_50",
}

# Sim-relevant buffs (placed on allies)
ALLY_BUFFS = {
    "counterattack", "block_damage", "block_debuffs", "unkillable",
    "atk_up", "atk_up_25", "inc_def", "inc_def_30", "inc_spd", "inc_spd_15",
    "cont_heal", "cont_heal_15", "ally_protect", "ally_protect_25",
    "strengthen", "strengthen_15", "shield", "inc_cr_30", "inc_cd_30",
}

def decode_status_effect(type_id: int) -> dict:
    """Decode a StatusEffectTypeId into sim-usable info."""
    info = STATUS_EFFECT_MAP.get(type_id)
    if info:
        name, is_debuff, is_buff = info
        return {"name": name, "is_debuff": is_debuff, "is_buff": is_buff, "type_id": type_id}
    return {"name": f"unknown_{type_id}", "is_debuff": False, "is_buff": False, "type_id": type_id}
