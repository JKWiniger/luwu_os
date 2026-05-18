#pragma once
// ============================================================================
// luwu-os 机型注册表（设计先行 / 数据驱动）
//
// 新增机型时**只需要在 DEVICES[] 里加一行**，无需改动任何 demo 标记或过滤代码。
// 已有 demo 中标注的 "@dog" / "@rider" 这类家族规则会自动覆盖新加入该家族的机型。
//
// 字段说明：
//   id     —— 设备 ID 字符串，必须与 detect_device.py 输出 / device.ini 内容一致。
//   family —— 所属家族（dog / rider / ... ），demo 用 "@xxx" 语法引用。
//   label  —— 仅用于日志和未来可能的 UI 展示，可不严格唯一。
// ============================================================================

struct DeviceEntry {
    const char* id;
    const char* family;
    const char* label;
};

static const DeviceEntry DEVICES[] = {
    // id              family    label
    {"xgomini",    "dog",   "XGO-MINI"   },
    {"xgolite",    "dog",   "XGO-LITE"   },
    {"xgomini2sw", "dog",   "XGO-MINI2SW"},
    {"xgomini3w",  "dog",   "XGO-MINI3W" },
    {"xgorider",   "rider", "XGO-RIDER"  },
    // 未来加机型示例（dog 家族新机）：
    // {"xgomini4", "dog",   "XGO-MINI4"  },
    // 未来加机型示例（新家族）：
    // {"xgocar",   "car",   "XGO-CAR"    },
};

static constexpr int DEVICE_COUNT = sizeof(DEVICES) / sizeof(DEVICES[0]);
