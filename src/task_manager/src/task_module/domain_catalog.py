"""Central domain catalogs for subtask planning.

Keep all frequently changed planning vocabularies in one place:
1) atomic actions and descriptions
2) canonical objects with default locations
3) reachable/operable locations
"""

ACTION_CATALOG = [
    {
        "id": 1,
        "signature": "PICK(object, hand)",
        "description": "Grasp an object at a specific location.",
    },
    {
        "id": 2,
        "signature": "PLACE(object, hand)",
        "description": "Put an object down at a specific location.",
    },
    {
        "id": 3,
        "signature": "POUR(source_object, target_object, hand)",
        "description": "Pour liquid from source (for example, milk, juice, or water bottle) into a target container (for example, cup or bowl). Prerequisite: both source and target must already be picked up or placed at the same location. This action depends on PICK of source and PICK/PLACE of target.",
    },
    {
        "id": 4,
        "signature": "HANDOVER(from_hand, to_hand)",
        "description": "Transfer an object between hands at the current position.",
    },
    {
        "id": 5,
        "signature": "STORE_ON_TRAY(object, hand)",
        "description": "Put an object onto the chest tray.",
    },
    {
        "id": 6,
        "signature": "RETRIEVE_FROM_TRAY(object, hand)",
        "description": "Pick an object from the chest tray.",
    },
    {
        "id": 7,
        "signature": "WAIT(seconds)",
        "description": "Wait for a specified duration.",
    },
    {
        "id": 8,
        "signature": "OPEN_DRAWER(hand)",
        "description": "Open a drawer (assume there is only one drawer in the environment).",
    },
    {
        "id": 9,
        "signature": "WATER_DISPENSER(hand)",
        "description": "Interact with the water dispenser (assume there is only one water dispenser in the environment).",
    },
    {
        "id": 10,
        "signature": "SCAN_TABLE_OBJECTS()",
        "description": "Use sensors to detect and identify objects on the table at the current location.",
    },
    {
        "id": 11,
        "signature": "OPEN_CABINET(location, hand)",
        "description": "Open a cabinet door. The parallel gripper can grasp the handle and pull it open. This becomes a mandatory prerequisite before taking items from inside the cabinet.",
    },
    {
        "id": 12,
        "signature": "CLOSE_CABINET(location, hand)",
        "description": "Close a cabinet door. Use this to restore the environment before leaving.",
    },
    {
        "id": 13,
        "signature": "CLOSE_DRAWER(hand)",
        "description": "Close a drawer. This action is typically paired with OPEN_DRAWER.",
    },
    {
        "id": 14,
        "signature": "PRESS_BUTTON(device_id, hand)",
        "description": "Press a button (for example, microwave switch or fan switch). The parallel gripper tip can be used for point pressing.",
    },
    {
        "id": 15,
        "signature": "WIPE_SURFACE(location, hand)",
        "description": "Wipe a surface at the location. Prerequisite: the hand must already hold a cloth or wet wipe.",
    },
]


# Canonical action execution times (seconds) used by fitness calculation.
# Key: action id in ACTION_CATALOG
ACTION_EXECUTION_TIME_SEC = {
    1: 55,
    2: 35,
    3: 110,
    4: 80,
    5: 45,
    6: 45,
    7: 60,
    8: 80,
    9: 115,
    10: 20,
    11: 110,
    12: 90,
    13: 60,
    14: 15,
    15: 30,
}


def get_action_execution_time_sec(action_id, default=None):
    """Return configured execution time (seconds) for an action id."""
    return ACTION_EXECUTION_TIME_SEC.get(action_id, default)


# Object risk coefficients used by fitness calculation.
# Higher value means the object should be handled more carefully.
OBJECT_RISK_COEF = {
    # Risk level 3: liquid containers that should avoid long travel.
    "water_cup": 3,
    "drink_cup": 3,
    "cup": 3,
    "green_cup": 3,

    # Risk level 2: sharp tools.
    "scissors": 2,
    "utility_knife": 2,

    # Risk level 1: seasonings / shakers.
    "salt_shaker": 1,
    "pepper_shaker": 1,
}


def get_object_risk_coef(object_name, default=0):
    """Return configured risk coefficient for an object name."""
    return OBJECT_RISK_COEF.get(object_name, default)


# Canonical movement-distance list between directly connected locations.
# Keep this separate from time; users can fill values later.
# Tuple format: (from_location_id, to_location_id, distance_m)
LOCATION_DISTANCE_EDGES_M = [
    # Example entry format (keep commented until real values are provided):
    # (1, 2, 3.5),
    (18, 1, 1.5),
    (18, 6, 2.5),
    (1, 2, 2),
    (2, 3, 1.5),
    (4, 1, 3.5),
    (2, 5, 3.7),
    (4, 5, 1.7),
    (4, 6, 1.5),
    (4, 20, 2),
    (5, 20, 2),
    # Kitchen area
    (5, 8, 1.8),
    (8, 9, 1.8),
    (8, 7, 0.8),
    # Hallway and rooms
    (2, 19, 3),
    (5, 19, 3.1),
    (19, 10, 1.5),
    (19, 11, 6.5),
    (19, 16, 5.0),
    (11, 12, 4.0),
    (11, 13, 2.5),
    (19, 14, 3.5),
    (14, 15, 1.5),
    (11, 16, 5.5),
    (16, 17, 2.0),
]

_LOCATION_DISTANCE_LOOKUP_M = {}
for src_id, dst_id, dist_m in LOCATION_DISTANCE_EDGES_M:
    _LOCATION_DISTANCE_LOOKUP_M[(src_id, dst_id)] = dist_m
    _LOCATION_DISTANCE_LOOKUP_M[(dst_id, src_id)] = dist_m


def get_direct_distance_m(start_location_id, end_location_id, default=None):
    """Return direct edge distance (meters) between two locations."""
    if start_location_id == end_location_id:
        return 0.0
    return _LOCATION_DISTANCE_LOOKUP_M.get((start_location_id, end_location_id), default)


# Canonical movement-time list (seconds) between directly connected locations.
# For non-adjacent locations, combine edges (for example with shortest-path).
LOCATION_TRAVEL_TIME_EDGES_SEC = [
    # Living room / entry / dining area
    (18, 1, 25),
    (18, 6, 30),
    (1, 2, 30),
    (2, 3, 35),
    (4, 1, 60),
    (2, 5, 60),
    (4, 5, 20),
    (4, 6, 28),
    (4, 20, 40),
    (5, 20, 30),
    # Kitchen area
    (5, 8, 35),
    (8, 9, 25),
    (8, 7, 20),
    # Hallway and rooms
    (2, 19, 40),
    (5, 19, 45),
    (19, 10, 15),
    (19, 11, 180),
    (19, 16, 140),
    (11, 12, 45),
    (11, 13, 25),
    (19, 14, 110),
    (14, 15, 20),
    (11, 16, 110),
    (16, 17, 35),
]

_LOCATION_TRAVEL_TIME_LOOKUP_SEC = {}
for src_id, dst_id, t_sec in LOCATION_TRAVEL_TIME_EDGES_SEC:
    _LOCATION_TRAVEL_TIME_LOOKUP_SEC[(src_id, dst_id)] = t_sec
    _LOCATION_TRAVEL_TIME_LOOKUP_SEC[(dst_id, src_id)] = t_sec


def get_direct_travel_time_sec(start_location_id, end_location_id, default=None):
    """Return direct edge movement time (seconds) between two locations."""
    if start_location_id == end_location_id:
        return 0
    return _LOCATION_TRAVEL_TIME_LOOKUP_SEC.get((start_location_id, end_location_id), default)

LOCATION_CATALOG = [
    {"location_id": 1, "zh_name": "電視櫃", "location_name": "tv_cabinet"},
    {"location_id": 2, "zh_name": "茶几", "location_name": "coffee_table"},
    {"location_id": 3, "zh_name": "沙發旁小圓桌", "location_name": "small_round_side_table"},
    {"location_id": 4, "zh_name": "餐桌", "location_name": "dining_table"},
    {"location_id": 5, "zh_name": "吧台", "location_name": "bar_counter"},
    {"location_id": 6, "zh_name": "零食櫃", "location_name": "snack_cabinet"},
    {"location_id": 7, "zh_name": "冰箱", "location_name": "fridge"},
    {"location_id": 8, "zh_name": "流理台", "location_name": "sink_counter"},
    {"location_id": 9, "zh_name": "瓦斯爐旁檯面", "location_name": "stove_side_counter"},
    {"location_id": 10, "zh_name": "櫥櫃", "location_name": "cabinet"},
    {"location_id": 11, "zh_name": "主臥床頭櫃", "location_name": "master_bedside_table"},
    {"location_id": 12, "zh_name": "主臥化妝台", "location_name": "master_vanity"},
    {"location_id": 13, "zh_name": "主臥書桌", "location_name": "master_desk"},
    {"location_id": 14, "zh_name": "客房床頭櫃", "location_name": "guest_bedside_table"},
    {"location_id": 15, "zh_name": "客房書桌", "location_name": "guest_desk"},
    {"location_id": 16, "zh_name": "書房電腦桌", "location_name": "study_computer_desk"},
    {"location_id": 17, "zh_name": "書房書架", "location_name": "bookshelf"},
    {"location_id": 18, "zh_name": "玄關鞋櫃", "location_name": "entry_shoe_cabinet"},
    {"location_id": 19, "zh_name": "走廊收納櫃", "location_name": "hallway_storage_cabinet"},
    {"location_id": 20, "zh_name": "飲水機", "location_name": "water_dispenser"},
]

# Backwards-compatible alias used by existing imports.
OPERABLE_LOCATIONS = LOCATION_CATALOG


# Default object placements are hints for the planner and can be overridden by
# per-task involved_items.
OBJECT_CATALOG = [
    {"zh_name": "果汁", "object_name": "juice", "location_name": "fridge", "location_id": 7},
    {"zh_name": "可樂", "object_name": "cola", "location_name": "fridge", "location_id": 7},
    {"zh_name": "水杯", "object_name": "water_cup", "location_name": "coffee_table", "location_id": 2},
    {"zh_name": "飲料杯", "object_name": "drink_cup", "location_name": "bar_counter", "location_id": 5},
    {"zh_name": "礦泉水", "object_name": "mineral_water", "location_name": "fridge", "location_id": 7},
    {"zh_name": "蘋果", "object_name": "apple", "location_name": "dining_table", "location_id": 4},
    {"zh_name": "香蕉", "object_name": "banana", "location_name": "dining_table", "location_id": 4},
    {"zh_name": "橘子", "object_name": "orange", "location_name": "dining_table", "location_id": 4},
    {"zh_name": "餅乾", "object_name": "cookie", "location_name": "snack_cabinet", "location_id": 6},
    {"zh_name": "檸檬", "object_name": "lemon", "location_name": "fridge", "location_id": 7},
    {"zh_name": "衛生紙", "object_name": "tissue_box", "location_name": "tv_cabinet", "location_id": 1},
    {"zh_name": "濕紙巾", "object_name": "wet_wipe", "location_name": "hallway_storage_cabinet", "location_id": 19},
    {"zh_name": "遙控器", "object_name": "remote_control", "location_name": "tv_cabinet", "location_id": 1},
    {"zh_name": "藥罐", "object_name": "medicine_jar", "location_name": "master_bedside_table", "location_id": 11},
    {"zh_name": "牛奶", "object_name": "milk", "location_name": "fridge", "location_id": 7},
    {"zh_name": "原子筆", "object_name": "pen", "location_name": "master_desk", "location_id": 13},
    {"zh_name": "筆記本", "object_name": "notebook", "location_name": "study_computer_desk", "location_id": 16},
    {"zh_name": "眼鏡盒", "object_name": "glasses_case", "location_name": "master_vanity", "location_id": 12},
    {"zh_name": "剪刀", "object_name": "scissors", "location_name": "study_computer_desk", "location_id": 16},
    {"zh_name": "膠帶", "object_name": "tape", "location_name": "study_computer_desk", "location_id": 16},
    {"zh_name": "美工刀", "object_name": "utility_knife", "location_name": "cabinet", "location_id": 10},
    {"zh_name": "菜瓜布", "object_name": "scrub_sponge", "location_name": "sink_counter", "location_id": 8},
    {"zh_name": "洗手乳", "object_name": "hand_soap", "location_name": "sink_counter", "location_id": 8},
    {"zh_name": "鹽巴罐", "object_name": "salt_shaker", "location_name": "stove_side_counter", "location_id": 9},
    {"zh_name": "沖泡粉包", "object_name": "instant_powder_packet", "location_name": "bar_counter", "location_id": 5},
    {"zh_name": "鑰匙串", "object_name": "keyring", "location_name": "entry_shoe_cabinet", "location_id": 18},
    {"zh_name": "梳子", "object_name": "comb", "location_name": "master_vanity", "location_id": 12},
    {"zh_name": "相機", "object_name": "camera", "location_name": "study_computer_desk", "location_id": 16},
    {"zh_name": "耳機", "object_name": "headphones", "location_name": "study_computer_desk", "location_id": 16},
    {"zh_name": "碗", "object_name": "bowl", "location_name": "cabinet", "location_id": 10},
    {"zh_name": "綠色杯子", "object_name": "green_cup", "location_name": "cabinet", "location_id": 10},
    {"zh_name": "杯子", "object_name": "cup", "location_name": "cabinet", "location_id": 10},
    {"zh_name": "drawer", "object_name": "drawer", "location_name": "cabinet", "location_id": 10},
    {"zh_name": "cabinet", "object_name": "cabinet", "location_name": "cabinet", "location_id": 10},
    {"zh_name": "抹布", "object_name": "cloth", "location_name": "sink_counter", "location_id": 8},
]
