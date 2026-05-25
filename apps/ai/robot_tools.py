# -*- coding: utf-8 -*-
"""
voice_chat.py 专用工具模块

独立于 agents/tools，避免模块耦合和循环导入问题。
返回纯字符串结果，直接供 voice_chat.py 的 ToolExecutor 使用。
"""

import os
import time
import base64
import requests
from typing import Dict, List, Optional, Any

# =============================================================
# 统一路径根
# =============================================================
_LUWU_ROOT = os.environ.get("LUWU_ROOT", "/opt/luwu-os")
_XGO_PICTURES = os.path.join(_LUWU_ROOT, "xgo-media/pictures")
_XGO_MUSIC = os.path.join(_LUWU_ROOT, "xgo-media/music")

# =============================================================
# XGO 硬件实例初始化
# =============================================================

_xgo_instance = None
_xgo_edu = None
_model_type = None
_init_done = False


def _init_xgo():
    """初始化 XGO 实例（复用检测时创建的实例，避免串口冲突）"""
    global _xgo_instance, _xgo_edu, _model_type, _init_done
    
    if _init_done:
        print(f"[robot_tools] _init_xgo 已初始化，机型={_model_type}, 硬件可用={_xgo_instance is not None}")
        return  # 已初始化
    _init_done = True
    
    # 步骤1: 先用 xgomini 创建实例读取固件版本
    try:
        from xgolib import XGO
        
        temp_instance = XGO("xgomini")
        firmware = temp_instance.read_firmware()
        print(f"[robot_tools] 固件版本: {firmware}")
        
        # 根据固件版本首字母判断机型
        if firmware and len(firmware) > 0:
            first_char = firmware[0].upper()
            if first_char == 'W':
                _model_type = 'xgomini3w'
            elif first_char == 'R':
                _model_type = 'xgorider'
            elif first_char == 'M':
                _model_type = 'xgomini'
            elif first_char == 'L':
                _model_type = 'xgolite'
            else:
                _model_type = 'xgomini'
                print(f"[robot_tools] 未知固件首字母 '{first_char}'，默认为 xgomini")
        else:
            _model_type = 'xgomini'
            print(f"[robot_tools] 固件版本为空，默认为 xgomini")
        
        # 步骤2: 根据检测到的机型创建正确的 XGO 实例
        if _model_type == 'xgorider':
            print(f"[robot_tools] 检测到 Rider 机型，重新创建 XGO('xgorider') 实例")
            try:
                _xgo_instance = XGO("xgorider")
                # 验证 Rider 实例是否具有必要的方法
                if not hasattr(_xgo_instance, 'rider_periodic_roll'):
                    print(f"⚠️ robot_tools: XGO('xgorider') 实例缺少 rider_periodic_roll 方法，类型={type(_xgo_instance).__name__}")
                    print(f"⚠️ robot_tools: 这可能是 xgolib 库版本问题，Rider 专有功能可能不可用")
            except Exception as e:
                print(f"⚠️ robot_tools: 创建 XGO('xgorider') 失败: {e}，回退到通用实例")
                _xgo_instance = temp_instance
        else:
            # 非 Rider 机型，复用已有实例
            _xgo_instance = temp_instance
        
        print(f"✓ robot_tools: 检测到机型 {_model_type}，实例类型={type(_xgo_instance).__name__}")
    except ImportError as e:
        print(f"⚠️ robot_tools: XGO库不可用 - {e}")
    except Exception as e:
        print(f"⚠️ robot_tools: XGO初始化失败 - {e}")
    
    # 步骤3: 初始化 XGOEDU（可选，用于屏幕显示和拍照）
    # 注意: edulib 在导入时会初始化 GPIO，单独处理避免阻塞
    try:
        from edulib import XGOEDU
        _xgo_edu = XGOEDU()
        print(f"✓ robot_tools: XGOEDU 初始化成功")
    except Exception as e:
        print(f"⚠️ robot_tools: XGOEDU不可用 - {e}，屏幕/拍照功能禁用")
        _xgo_edu = None


def get_model_type() -> str:
    """获取当前机型"""
    _init_xgo()
    return _model_type or 'xgomini'


def is_hardware_available() -> bool:
    """检查硬件是否可用"""
    _init_xgo()
    return _xgo_instance is not None


def get_xgo_edu():
    """获取 XGOEDU 实例（用于屏幕显示）"""
    _init_xgo()
    return _xgo_edu


# =============================================================
# 通用工具定义 (OpenAI Function Call 格式)
# =============================================================

COMMON_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "xgo_move",
            "description": "控制XGO机器人移动。direction: forward(前进)/backward(后退)/left(左移)/right(右移)，step: 移动步数(秒)",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["forward", "backward", "left", "right"]},
                    "step": {"type": "number", "description": "移动时长(秒)", "default": 3}
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_action",
            "description": "执行预设动作。action_id: 1=趴下, 2=站起, 3=匍匐前进, 4=转圈, 5=踏步, 6=蹲起, 7=转动Roll, 8=转动Pitch, 9=转动Yaw, 10=三轴转动, 11=撒尿, 12=坐下, 13=招手, 14=伸懒腰, 15=波浪, 16=摇摆, 17=乞讨, 18=找食物, 19=握手, 20=鸡头, 21=俯卧撑, 22=张望, 23=跳舞, 24=调皮, 128=上抓, 129=中抓, 130=下抓, 144=上楼梯, 255=重置",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "string", "description": "动作ID", "enum": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "128", "129", "130", "144", "255"]}
                },
                "required": ["action_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_turn",
            "description": "控制XGO机器人转向。direction: left(左转)/right(右转)，angle: 转向角度(1-180度)",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["left", "right"]},
                    "angle": {"type": "number", "description": "转向角度", "default": 90}
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_photo_understand",
            "description": "拍照并用AI视觉模型理解图片内容。用于看看周围环境、识别物体、找人、找东西等场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "对图片的提问", "default": "图中描绘的是什么景象?"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_battery",
            "description": "读取XGO机器狗电池电量百分比",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_stop",
            "description": "停止XGO机器狗当前运动",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_reset",
            "description": "重置XGO机器狗到初始标准状态",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_display_clear",
            "description": "清除XGO屏幕显示",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_display_text",
            "description": "XGO屏幕显示文字",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要显示的文字内容"},
                    "x": {"type": "number", "description": "X坐标", "default": 5},
                    "y": {"type": "number", "description": "Y坐标", "default": 5},
                    "fontsize": {"type": "number", "description": "字体大小", "default": 15}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_read_imu",
            "description": "读取XGO机器人IMU数据(roll/pitch/yaw)",
            "parameters": {
                "type": "object",
                "properties": {
                    "axis": {"type": "string", "enum": ["roll", "pitch", "yaw"], "description": "要读取的轴向"}
                },
                "required": ["axis"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_display_picture",
            "description": "在XGO屏幕上显示本地图片(位于xgo-media/pictures/目录)",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "图片文件名(jpg格式)"},
                    "x": {"type": "number", "description": "X坐标", "default": 0},
                    "y": {"type": "number", "description": "Y坐标", "default": 0}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_speak",
            "description": "XGO播放本地音频文件(位于xgo-media/music/目录)",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "音频文件名"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_play_http_audio",
            "description": "XGO播放网络音频URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "音频文件的HTTP URL"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_display_http_image",
            "description": "XGO显示网络图片URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "图片文件的HTTP URL"},
                    "x": {"type": "number", "description": "X坐标", "default": 0},
                    "y": {"type": "number", "description": "Y坐标", "default": 0}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_generate_and_display_image",
            "description": "使用AI生成图片并在XGO屏幕上显示",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "图片生成提示词"},
                    "size": {"type": "string", "description": "图片尺寸", "default": "960*720"}
                },
                "required": ["prompt"]
            }
        }
    },
]

# Mini/Lite/Mini3W 专用工具
QUADRUPED_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "xgo_translation",
            "description": "控制机身平移。axis: x(前后)/y(左右)/z(上下身高)，distance: 平移距离(mm)",
            "parameters": {
                "type": "object",
                "properties": {
                    "axis": {"type": "string", "enum": ["x", "y", "z"]},
                    "distance": {"type": "number", "description": "平移距离(mm)"}
                },
                "required": ["axis", "distance"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_attitude",
            "description": "调整机身姿态。direction: r(Roll横滚)/p(Pitch俯仰)/y(Yaw偏航)，angle: 角度",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["r", "p", "y"]},
                    "angle": {"type": "number", "description": "角度"}
                },
                "required": ["direction", "angle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_arm_control",
            "description": "机械臂控制。action: open(张开夹爪)/close(闭合夹爪)/up(抬起)/down(放下)",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["open", "close", "up", "down"]}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_find_person",
            "description": "XGO机器狗寻找人类目标（使用人脸检测）",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_search_time": {"type": "number", "description": "最大搜索时间(秒)", "default": 45}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_mark_time",
            "description": "控制机器狗原地踏步",
            "parameters": {
                "type": "object",
                "properties": {
                    "step": {"type": "number", "description": "抬腿高度(mm)，范围[10, 35]"}
                },
                "required": ["step"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_periodic_tran",
            "description": "控制机器狗进行周期性往复平移运动",
            "parameters": {
                "type": "object",
                "properties": {
                    "axis": {"type": "string", "enum": ["x", "y", "z"], "description": "平移轴向"},
                    "period": {"type": "number", "description": "周期时间(秒)，范围[1.5, 8]"},
                    "wait_time": {"type": "number", "description": "运动持续时间(秒)", "default": 5}
                },
                "required": ["axis", "period"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_periodic_rot",
            "description": "控制机器狗进行周期性往复旋转运动(摇摆)",
            "parameters": {
                "type": "object",
                "properties": {
                    "axis": {"type": "string", "enum": ["r", "p", "y"], "description": "旋转轴向"},
                    "period": {"type": "number", "description": "周期时间(秒)，范围[1.5, 8]"},
                    "wait_time": {"type": "number", "description": "运动持续时间(秒)", "default": 5}
                },
                "required": ["axis", "period"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_gait_type",
            "description": "设置机器狗步态类型",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["trot", "walk", "high_walk", "slow_trot"], "description": "trot=小跑, walk=行走, high_walk=高抬腿, slow_trot=慢速"}
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_pace",
            "description": "设置机器狗步伐频率",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["normal", "slow", "high"], "description": "normal=正常, slow=慢速, high=高速"}
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_imu",
            "description": "开启/关闭IMU自稳功能",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "number", "description": "0=关闭自稳, 1=开启自稳"}
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_leg",
            "description": "控制单条腿的位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "leg_id": {"type": "number", "description": "腿编号 (1=左前, 2=右前, 3=右后, 4=左后)"},
                    "x": {"type": "number", "description": "X轴位置(mm)"},
                    "y": {"type": "number", "description": "Y轴位置(mm)"},
                    "z": {"type": "number", "description": "Z轴位置(mm)"}
                },
                "required": ["leg_id", "x", "y", "z"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_motor",
            "description": "控制单个舵机角度",
            "parameters": {
                "type": "object",
                "properties": {
                    "motor_id": {"type": "number", "description": "舵机编号(11-13左前, 21-23右前, 31-33右后, 41-43左后, 51机械臂)"},
                    "angle": {"type": "number", "description": "目标角度"}
                },
                "required": ["motor_id", "angle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_find_ball",
            "description": "寻找指定颜色的小球",
            "parameters": {
                "type": "object",
                "properties": {
                    "color": {"type": "string", "enum": ["red", "green", "blue"], "description": "小球颜色"},
                    "max_search_time": {"type": "number", "description": "最大搜索时间(秒)", "default": 30}
                },
                "required": ["color"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xgo_catch_ball",
            "description": "XGO机器狗识别并抓取指定颜色的小球（完整抓取流程，包括搜索、跟踪、抓取）",
            "parameters": {
                "type": "object",
                "properties": {
                    "color": {"type": "string", "enum": ["red", "green", "blue"], "description": "要抓取的小球颜色"},
                    "max_search_time": {"type": "number", "description": "最大搜索时间(秒)", "default": 30},
                    "max_grab_attempts": {"type": "number", "description": "最大抓取尝试次数", "default": 3}
                },
                "required": ["color"]
            }
        }
    },
]

# Rider 专用工具
RIDER_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "xgo_action",
            "description": "执行Rider预设动作。action_id: 1=左右摇摆, 2=高低起伏, 3=前进后退, 4=四方蛇形, 5=升降旋转, 6=圆周晃动, 255=重置",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "string", "description": "动作ID(1-6, 255)", "enum": ["1", "2", "3", "4", "5", "6", "255"]}
                },
                "required": ["action_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_roll",
            "description": "调整Rider机身横滚角",
            "parameters": {
                "type": "object",
                "properties": {
                    "angle": {"type": "number", "description": "角度范围[-17, 17]"}
                },
                "required": ["angle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_height",
            "description": "调整Rider身高",
            "parameters": {
                "type": "object",
                "properties": {
                    "height": {"type": "number", "description": "高度范围[60, 120]mm"}
                },
                "required": ["height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_led",
            "description": "控制Rider LED灯颜色",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "number", "description": "LED编号(0-5)"},
                    "r": {"type": "number", "description": "红色(0-255)"},
                    "g": {"type": "number", "description": "绿色(0-255)"},
                    "b": {"type": "number", "description": "蓝色(0-255)"}
                },
                "required": ["index", "r", "g", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_turn",
            "description": "控制Rider原地旋转。speed: 角速度[-360, 360]°/s，正值左转，负值右转。runtime: 旋转时间(秒)",
            "parameters": {
                "type": "object",
                "properties": {
                    "speed": {"type": "number", "description": "角速度，范围[-360, 360]"},
                    "runtime": {"type": "number", "description": "持续时间(秒)", "default": 0}
                },
                "required": ["speed"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_perform",
            "description": "开启/关闭Rider循环表演模式",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "number", "description": "0=关闭表演, 1=开启表演"}
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_periodic_roll",
            "description": "控制Rider进行周期性Roll轴摇摆",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "number", "description": "周期时间[1, 2]秒，0停止"},
                    "wait_time": {"type": "number", "description": "运动持续时间(秒)", "default": 0}
                },
                "required": ["period"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_periodic_z",
            "description": "控制Rider进行周期性Z轴升降",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "number", "description": "周期时间[1, 2]秒，0停止"},
                    "wait_time": {"type": "number", "description": "运动持续时间(秒)", "default": 0}
                },
                "required": ["period"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_balance_roll",
            "description": "开启/关闭Rider Roll轴自平衡",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "number", "description": "0=关闭, 1=开启"}
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_reset_odom",
            "description": "重置Rider里程计",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rider_calibration",
            "description": "校准Rider机器人",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "enum": ["start", "end"], "description": "start=开始校准, end=结束校准"}
                },
                "required": ["state"]
            }
        }
    },
]


def get_tool_definitions() -> List[Dict]:
    """根据机型获取工具定义列表"""
    _init_xgo()
    tools = list(COMMON_TOOL_DEFINITIONS)
    
    model = _model_type or 'xgomini'
    print(f"[robot_tools] get_tool_definitions: 当前机型={model}")
    
    if model == 'xgorider':
        # Rider 机型：需要用 Rider 专属的 xgo_action 替换通用版本
        # 先移除通用的 xgo_action
        tools = [t for t in tools if t['function']['name'] != 'xgo_action']
        tools.extend(RIDER_TOOL_DEFINITIONS)
        print(f"[robot_tools] 添加 Rider 专用工具，共 {len(RIDER_TOOL_DEFINITIONS)} 个")
    else:
        # Mini / Lite / Mini3W 共用四足工具
        tools.extend(QUADRUPED_TOOL_DEFINITIONS)
        print(f"[robot_tools] 添加四足专用工具，共 {len(QUADRUPED_TOOL_DEFINITIONS)} 个")
    
    # 打印工具名称列表
    tool_names = [t['function']['name'] for t in tools]
    print(f"[robot_tools] 工具列表({len(tools)}个): {tool_names}")
    
    return tools


# =============================================================
# 工具执行函数
# =============================================================

def execute_tool(tool_name: str, arguments: Dict, api_key: str = None) -> str:
    """
    执行工具并返回字符串结果
    
    Args:
        tool_name: 工具名称
        arguments: 工具参数字典
        api_key: API密钥（用于AI功能）
    
    Returns:
        执行结果字符串
    """
    _init_xgo()
    
    print(f"[robot_tools] execute_tool: 工具={tool_name}, 当前机型={_model_type}, 硬件可用={_xgo_instance is not None}")
    print(f"[robot_tools] execute_tool: 参数={arguments}")
    
    # 模拟模式检查
    if not is_hardware_available():
        result = f"[模拟] {tool_name}({arguments})"
        print(f"[robot_tools] execute_tool: 模拟模式返回={result}")
        return result
    
    try:
        # ============ 通用工具 ============
        if tool_name == "xgo_move":
            result = _execute_move(arguments)
        
        elif tool_name == "xgo_action":
            result = _execute_action(arguments)
        
        elif tool_name == "xgo_turn":
            result = _execute_turn(arguments)
        
        elif tool_name == "xgo_photo_understand":
            result = _execute_photo_understand(arguments, api_key)
        
        elif tool_name == "xgo_battery":
            result = _execute_battery()
        
        elif tool_name == "xgo_stop":
            result = _execute_stop()
        
        elif tool_name == "xgo_reset":
            result = _execute_reset()
        
        elif tool_name == "xgo_display_clear":
            result = _execute_display_clear()
        
        elif tool_name == "xgo_display_text":
            result = _execute_display_text(arguments)
        
        elif tool_name == "xgo_read_imu":
            result = _execute_read_imu(arguments)
        
        # ============ 四足专用工具 ============
        elif tool_name == "xgo_translation":
            result = _execute_translation(arguments)
        
        elif tool_name == "xgo_attitude":
            result = _execute_attitude(arguments)
        
        # ============ Rider专用工具 ============
        elif tool_name == "rider_roll":
            result = _execute_rider_roll(arguments)
        
        elif tool_name == "rider_height":
            result = _execute_rider_height(arguments)
        
        elif tool_name == "rider_led":
            result = _execute_rider_led(arguments)
        
        elif tool_name == "rider_turn":
            result = _execute_rider_turn(arguments)
        
        elif tool_name == "rider_perform":
            result = _execute_rider_perform(arguments)
        
        elif tool_name == "rider_periodic_roll":
            result = _execute_rider_periodic_roll(arguments)
        
        elif tool_name == "rider_periodic_z":
            result = _execute_rider_periodic_z(arguments)
        
        elif tool_name == "rider_balance_roll":
            result = _execute_rider_balance_roll(arguments)
        
        # ============ 四足专用工具 ============
        elif tool_name == "xgo_arm_control":
            result = _execute_arm_control(arguments)
        
        elif tool_name == "xgo_find_person":
            result = _execute_find_person(arguments)
        
        elif tool_name == "xgo_mark_time":
            result = _execute_mark_time(arguments)
        
        elif tool_name == "xgo_periodic_tran":
            result = _execute_periodic_tran(arguments)
        
        elif tool_name == "xgo_periodic_rot":
            result = _execute_periodic_rot(arguments)
        
        elif tool_name == "xgo_gait_type":
            result = _execute_gait_type(arguments)
        
        elif tool_name == "xgo_pace":
            result = _execute_pace(arguments)
        
        elif tool_name == "xgo_imu":
            result = _execute_imu(arguments)
        
        elif tool_name == "xgo_leg":
            result = _execute_leg(arguments)
        
        elif tool_name == "xgo_motor":
            result = _execute_motor(arguments)
        
        elif tool_name == "xgo_find_ball":
            result = _execute_find_ball(arguments)
        
        elif tool_name == "xgo_catch_ball":
            result = _execute_catch_ball(arguments)
        
        # ============ 通用媒体工具 ============
        elif tool_name == "xgo_display_picture":
            result = _execute_display_picture(arguments)
        
        elif tool_name == "xgo_speak":
            result = _execute_speak(arguments)
        
        elif tool_name == "xgo_play_http_audio":
            result = _execute_play_http_audio(arguments)
        
        elif tool_name == "xgo_display_http_image":
            result = _execute_display_http_image(arguments)
        
        elif tool_name == "xgo_generate_and_display_image":
            result = _execute_generate_and_display_image(arguments, api_key)
        
        # ============ Rider额外工具 ============
        elif tool_name == "rider_reset_odom":
            result = _execute_rider_reset_odom()
        
        elif tool_name == "rider_calibration":
            result = _execute_rider_calibration(arguments)
        
        else:
            result = f"未知工具: {tool_name}"
        
        print(f"[robot_tools] execute_tool: 返回结果={result}")
        return result
    
    except Exception as e:
        result = f"工具执行错误: {str(e)}"
        print(f"[robot_tools] execute_tool: 异常={result}")
        return result


# =============================================================
# 工具执行实现
# =============================================================

def _execute_move(args: Dict) -> str:
    """移动"""
    direction = args.get("direction", "forward")
    step = args.get("step", 3)
    
    model = _model_type or 'xgomini'
    
    if model == 'xgorider':
        # Rider 使用 rider_move_x
        speed = 0.5 if direction in ["forward", "backward"] else 0
        if direction == "backward":
            speed = -speed
        _xgo_instance.rider_move_x(speed, int(step))
        return f"✓ Rider {direction} 移动完成"
    else:
        # 四足机器人
        direction_map = {
            "forward": ("x", 15),
            "backward": ("x", -15),
            "left": ("y", 10),
            "right": ("y", -10)
        }
        axis, value = direction_map.get(direction, ("x", 15))
        _xgo_instance.move(axis, value)
        time.sleep(step)
        _xgo_instance.reset()
        
        dir_name = {"forward": "前进", "backward": "后退", "left": "左移", "right": "右移"}
        return f"✓ 机器人{dir_name.get(direction, direction)}移动完成"


def _execute_action(args: Dict) -> str:
    """执行预设动作"""
    action_id = args.get("action_id")
    
    # 兼容旧的 action_name 参数
    if action_id is None:
        action_name = args.get("action_name", "stand")
        # 旧格式映射到新格式
        old_action_map = {
            "sit": 12, "stand": 2, "wave": 13, "dance": 23,
            "shake_hands": 19, "push_up": 21
        }
        action_id = old_action_map.get(action_name, 2)
    
    # 将字符串类型的 action_id 转换为整数(Gemini API 要求 enum 为字符串)
    if isinstance(action_id, str):
        action_id = int(action_id)
    
    model = _model_type or 'xgomini'
    
    if model == 'xgorider':
        # Rider 的动作映射
        rider_action_names = {
            1: "左右摇摆", 2: "高低起伏", 3: "前进后退",
            4: "四方蛇形", 5: "升降旋转", 6: "圆周晃动",
            255: "重置"
        }
        rider_action_sleep_times = {
            1: 3, 2: 4, 3: 3, 4: 4, 5: 6, 6: 5, 255: 1
        }
        
        _xgo_instance.rider_action(action_id, wait=True)
        sleep_time = rider_action_sleep_times.get(action_id, 3)
        action_name = rider_action_names.get(action_id, f"动作{action_id}")
    else:
        # 四足机器人的动作映射
        action_names = {
            1: "趴下", 2: "站起", 3: "匍匐前进", 4: "转圈", 5: "踏步",
            6: "蹲起", 7: "转动Roll", 8: "转动Pitch", 9: "转动Yaw", 10: "三轴转动",
            11: "撒尿", 12: "坐下", 13: "招手", 14: "伸懒腰", 15: "波浪",
            16: "摇摆", 17: "乞讨", 18: "找食物", 19: "握手", 20: "鸡头",
            21: "俯卧撑", 22: "张望", 23: "跳舞", 24: "调皮",
            128: "上抓", 129: "中抓", 130: "下抓", 144: "上楼梯",
            255: "重置"
        }
        action_sleep_times = {
            1: 3, 2: 3, 3: 5, 4: 4, 5: 5, 6: 4, 7: 4, 8: 4, 9: 4, 10: 7,
            11: 7, 12: 5, 13: 7, 14: 10, 15: 6, 16: 6, 17: 6, 18: 6, 19: 10,
            20: 9, 21: 8, 22: 8, 23: 6, 24: 7,
            128: 10, 129: 10, 130: 10, 144: 12,
            255: 1
        }
        
        _xgo_instance.action(action_id)
        sleep_time = action_sleep_times.get(action_id, 3)
        time.sleep(sleep_time)
        action_name = action_names.get(action_id, f"动作{action_id}")
    
    return f"✓ 执行动作: {action_name}"


def _execute_turn(args: Dict) -> str:
    """转向"""
    direction = args.get("direction", "left")
    angle = args.get("angle", 90)
    
    model = _model_type or 'xgomini'
    
    if model == 'xgorider':
        speed = 60 if direction == "left" else -60
        runtime = angle / 60  # 估算时间
        _xgo_instance.rider_turn(speed, int(runtime))
    else:
        step = 18 if direction == "left" else -18
        _xgo_instance.turn(step)
        time.sleep(angle / 30)
        _xgo_instance.reset()
    
    dir_name = "左转" if direction == "left" else "右转"
    return f"✓ 机器人{dir_name}{angle}度"


def _execute_photo_understand(args: Dict, api_key: str) -> str:
    """拍照理解"""
    prompt = args.get("prompt", "图中描绘的是什么景象?")
    
    if not api_key:
        return "❌ 未提供API密钥，无法调用视觉理解服务"
    
    if _xgo_edu is None:
        return "❌ 摄像头不可用（可能处于模拟模式）"
    
    try:
        import cv2
        
        photo_path = os.path.join(_XGO_PICTURES, "voice_chat_photo.jpg")
        
        # 显示拍照状态
        try:
            _xgo_edu.lcd_clear()
            _xgo_edu.lcd_text(5, 5, "正在拍照...", 14)
        except:
            pass
        
        _xgo_edu.camera_still = False
        time.sleep(0.6)
        
        if _xgo_edu.picam2 is None:
            _xgo_edu.open_camera()
        
        image = _xgo_edu.picam2.capture_array()
        cv2.imwrite(photo_path, image)
        
        try:
            _xgo_edu.lcd_text(5, 30, "AI分析中...", 12)
        except:
            pass
        
        if not os.path.exists(photo_path):
            return "❌ 照片文件不存在"
        
        with open(photo_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "qwen-vl-max",
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": "你是一个视觉助手，请简洁地描述图片内容。"}]},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                    {"type": "text", "text": prompt}
                ]}
            ]
        }
        
        response = requests.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                answer = result["choices"][0]["message"]["content"]
                
                try:
                    display_text = answer[:50] + "..." if len(answer) > 50 else answer
                    _xgo_edu.lcd_clear()
                    _xgo_edu.lcd_text(5, 5, "图片理解结果:", 12)
                    _xgo_edu.lcd_text(5, 25, display_text, 10)
                except:
                    pass
                
                return f"拍照理解结果:\n问题: {prompt}\n回答: {answer}"
            else:
                return "❌ VL模型返回数据格式异常"
        else:
            return f"❌ VL模型请求失败: {response.status_code}"
    
    except Exception as e:
        return f"❌ 拍照理解失败: {str(e)}"


def _execute_battery() -> str:
    """读取电量"""
    model = _model_type or 'xgomini'
    
    try:
        if model == 'xgorider':
            battery = _xgo_instance.rider_read_battery()
        else:
            battery = _xgo_instance.read_battery()
        return f"🔋 当前电池电量: {battery}%"
    except Exception as e:
        return f"❌ 读取电量失败: {str(e)}"


def _execute_stop() -> str:
    """停止"""
    try:
        _xgo_instance.stop()
        return "✓ 机器人已停止"
    except Exception as e:
        return f"❌ 停止失败: {str(e)}"


def _execute_reset() -> str:
    """重置"""
    model = _model_type or 'xgomini'
    
    try:
        if model == 'xgorider':
            _xgo_instance.rider_reset()
        else:
            _xgo_instance.reset()
        time.sleep(2)
        return "✓ 机器人已重置"
    except Exception as e:
        return f"❌ 重置失败: {str(e)}"


def _execute_display_clear() -> str:
    """清屏"""
    if _xgo_edu is None:
        return "❌ 屏幕不可用"
    
    try:
        _xgo_edu.lcd_clear()
        return "✓ 屏幕已清除"
    except Exception as e:
        return f"❌ 清屏失败: {str(e)}"


def _execute_display_text(args: Dict) -> str:
    """显示文字"""
    text = args.get("text", "")
    x = args.get("x", 5)
    y = args.get("y", 5)
    fontsize = args.get("fontsize", 15)
    
    if _xgo_edu is None:
        return "❌ 屏幕不可用"
    
    try:
        # lcd_text 签名: lcd_text(x, y, text, fontsize)
        _xgo_edu.lcd_text(x, y, text, fontsize)
        return f"✓ 屏幕显示: {text}"
    except Exception as e:
        return f"❌ 显示失败: {str(e)}"


def _execute_read_imu(args: Dict) -> str:
    """读取IMU"""
    axis = args.get("axis", "roll")
    model = _model_type or 'xgomini'
    
    try:
        if model == 'xgorider':
            if axis == "roll":
                value = _xgo_instance.rider_read_roll()
            elif axis == "pitch":
                value = _xgo_instance.rider_read_pitch()
            elif axis == "yaw":
                value = _xgo_instance.rider_read_yaw()
            else:
                return f"❌ 不支持的轴向: {axis}"
        else:
            if axis == "roll":
                value = _xgo_instance.read_roll()
            elif axis == "pitch":
                value = _xgo_instance.read_pitch()
            elif axis == "yaw":
                value = _xgo_instance.read_yaw()
            else:
                return f"❌ 不支持的轴向: {axis}"
        
        axis_names = {"roll": "横滚角", "pitch": "俯仰角", "yaw": "偏航角"}
        return f"📐 {axis_names.get(axis, axis)}: {value}°"
    except Exception as e:
        return f"❌ 读取IMU失败: {str(e)}"


def _execute_translation(args: Dict) -> str:
    """平移（四足专用）"""
    axis = args.get("axis", "z")
    distance = args.get("distance", 100)
    
    try:
        _xgo_instance.translation(axis.lower(), distance)
        time.sleep(1)
        dir_name = {"x": "前后", "y": "左右", "z": "上下"}.get(axis.lower(), axis)
        return f"✓ 机身{dir_name}平移完成({distance}mm)"
    except Exception as e:
        return f"❌ 平移失败: {str(e)}"


def _execute_attitude(args: Dict) -> str:
    """姿态调整（四足专用）"""
    direction = args.get("direction", "p")
    angle = args.get("angle", 0)
    
    try:
        _xgo_instance.attitude(direction, angle)
        time.sleep(1.5)
        axis_names = {"r": "Roll", "p": "Pitch", "y": "Yaw"}
        return f"✓ {axis_names.get(direction, direction)}调整至{angle}°"
    except Exception as e:
        return f"❌ 姿态调整失败: {str(e)}"


def _execute_rider_roll(args: Dict) -> str:
    """Rider横滚角"""
    model = _model_type or 'xgomini'
    if model != 'xgorider':
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    angle = args.get("angle", 0)
    
    try:
        _xgo_instance.rider_roll(angle)
        time.sleep(1)
        return f"✓ Rider Roll调整至{angle}°"
    except Exception as e:
        return f"❌ Rider Roll调整失败: {str(e)}"


def _execute_rider_height(args: Dict) -> str:
    """Rider身高"""
    model = _model_type or 'xgomini'
    if model != 'xgorider':
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    height = args.get("height", 90)
    
    try:
        _xgo_instance.rider_height(height)
        time.sleep(1)
        return f"✓ Rider身高调整至{height}mm"
    except Exception as e:
        return f"❌ Rider身高调整失败: {str(e)}"


def _execute_rider_led(args: Dict) -> str:
    """Rider LED"""
    model = _model_type or 'xgomini'
    if model != 'xgorider':
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    index = args.get("index", 0)
    r = args.get("r", 0)
    g = args.get("g", 0)
    b = args.get("b", 0)
    
    try:
        _xgo_instance.rider_led(index, [r, g, b])
        time.sleep(0.2)
        return f"✓ LED{index}颜色设置为RGB({r},{g},{b})"
    except Exception as e:
        return f"❌ LED控制失败: {str(e)}"


def _execute_rider_turn(args: Dict) -> str:
    """Rider旋转"""
    model = _model_type or 'xgomini'
    if model != 'xgorider':
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    speed = args.get("speed", 60)
    runtime = args.get("runtime", 0)
    
    try:
        _xgo_instance.rider_turn(speed, int(runtime))
        direction = "左转" if speed > 0 else "右转"
        if runtime > 0:
            return f"✓ Rider{direction}旋转(角速度{speed}°/s, 持续{runtime}秒)"
        else:
            return f"✓ Rider{direction}旋转(角速度{speed}°/s)"
    except Exception as e:
        return f"❌ Rider旋转失败: {str(e)}"


def _execute_rider_perform(args: Dict) -> str:
    """Rider表演模式"""
    model = _model_type or 'xgomini'
    if model != 'xgorider':
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    mode = args.get("mode", 0)
    
    try:
        if mode not in [0, 1]:
            return "❌ 模式参数错误，必须为0(关闭)或1(开启)"
        _xgo_instance.rider_perform(mode)
        time.sleep(0.3)
        status = "开启" if mode == 1 else "关闭"
        return f"✓ Rider表演模式已{status}"
    except Exception as e:
        return f"❌ 表演模式设置失败: {str(e)}"


def _execute_rider_periodic_roll(args: Dict) -> str:
    """Rider周期性Roll摇摆"""
    model = _model_type or 'xgomini'
    print(f"[robot_tools] _execute_rider_periodic_roll: 检查机型, _model_type={_model_type}, model={model}")
    
    if model != 'xgorider':
        print(f"[robot_tools] _execute_rider_periodic_roll: 机型不匹配，拒绝执行")
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    # 防御性检查：验证实例是否具有该方法
    if not hasattr(_xgo_instance, 'rider_periodic_roll'):
        instance_type = type(_xgo_instance).__name__ if _xgo_instance else 'None'
        print(f"[robot_tools] _execute_rider_periodic_roll: 实例缺少方法, 实例类型={instance_type}")
        return f"❌ 当前XGO实例不支持此功能（实例类型: {instance_type}），可能需要更新xgolib库"
    
    period = args.get("period", 1.5)
    wait_time = args.get("wait_time", 0)
    print(f"[robot_tools] _execute_rider_periodic_roll: 准备执行, period={period}, wait_time={wait_time}")
    
    try:
        print(f"[robot_tools] _execute_rider_periodic_roll: 调用 _xgo_instance.rider_periodic_roll({period})")
        _xgo_instance.rider_periodic_roll(period)
        print(f"[robot_tools] _execute_rider_periodic_roll: rider_periodic_roll 调用成功")
        
        if wait_time > 0:
            print(f"[robot_tools] _execute_rider_periodic_roll: 等待 {wait_time} 秒...")
            time.sleep(wait_time)
            print(f"[robot_tools] _execute_rider_periodic_roll: 停止摇摆")
            _xgo_instance.rider_periodic_roll(0)
            return f"✓ Rider周期性Roll摇摆完成(周期{period}秒, 持续{wait_time}秒)"
        else:
            return f"✓ Rider开始周期性Roll摇摆(周期{period}秒)"
    except Exception as e:
        print(f"[robot_tools] _execute_rider_periodic_roll: 异常={e}")
        import traceback
        traceback.print_exc()
        return f"❌ 周期性摇摆失败: {str(e)}"


def _execute_rider_periodic_z(args: Dict) -> str:
    """Rider周期性Z轴升降"""
    model = _model_type or 'xgomini'
    if model != 'xgorider':
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    period = args.get("period", 1.5)
    wait_time = args.get("wait_time", 0)
    
    try:
        _xgo_instance.rider_periodic_z(period)
        if wait_time > 0:
            time.sleep(wait_time)
            _xgo_instance.rider_periodic_z(0)
            return f"✓ Rider周期性升降完成(周期{period}秒, 持续{wait_time}秒)"
        else:
            return f"✓ Rider开始周期性升降(周期{period}秒)"
    except Exception as e:
        return f"❌ 周期性升降失败: {str(e)}"


def _execute_rider_balance_roll(args: Dict) -> str:
    """Rider Roll轴自平衡"""
    model = _model_type or 'xgomini'
    if model != 'xgorider':
        return f"❌ 此功能仅支持Rider机型，当前机型为{model}"
    
    mode = args.get("mode", 0)
    
    try:
        if mode not in [0, 1]:
            return "❌ 模式参数错误，必须为0(关闭)或1(开启)"
        _xgo_instance.rider_balance_roll(mode)
        time.sleep(0.3)
        status = "开启" if mode == 1 else "关闭"
        return f"✓ Rider Roll轴自平衡已{status}"
    except Exception as e:
        return f"❌ 自平衡设置失败: {str(e)}"


def _execute_arm_control(args: Dict) -> str:
    """机械臂控制"""
    action = args.get("action", "open")
    
    try:
        # claw() 方法只接受一个参数：夹爪开合度
        # 0 = 完全闭合, 255 = 完全张开
        action_map = {
            "open": 255,    # 张开夹爪
            "close": 0,     # 闭合夹爪
            "up": 255,      # 抬起（张开）
            "down": 0       # 放下（闭合）
        }
        
        if action not in action_map:
            return f"❌ 未知的机械臂动作: {action}, 支持: open, close, up, down"
        
        claw_value = action_map[action]
        _xgo_instance.claw(claw_value)
        time.sleep(1.5)
        
        action_name = {"open": "张开", "close": "闭合", "up": "抬起", "down": "放下"}.get(action, action)
        return f"✓ 机械臂{action_name}动作完成"
    except Exception as e:
        return f"❌ 机械臂控制失败: {str(e)}"


def _execute_find_person(args: Dict) -> str:
    """寻找人类目标"""
    max_search_time = args.get("max_search_time", 45.0)
    
    if _xgo_edu is None:
        return "❌ 摄像头不可用"
    
    try:
        # 确保摄像头可用
        try:
            _xgo_edu.open_camera()
            time.sleep(1)
        except Exception as cam_e:
            return f"❌ 摄像头初始化失败: {str(cam_e)}"
        
        start_time = time.time()
        found = False
        
        while time.time() - start_time < max_search_time:
            try:
                face_rect = _xgo_edu.face_detect()
                
                if face_rect is not None:
                    found = True
                    x, y, w, h = face_rect
                    return f"✓ 找到人类目标！位置:({int(x)}, {int(y)}), 大小:{int(w)}x{int(h)}"
            except:
                pass
            time.sleep(0.1)
        
        return "❌ 搜索超时，未找到人类目标"
    except Exception as e:
        return f"❌ 人类搜索失败: {str(e)}"


def _execute_mark_time(args: Dict) -> str:
    """原地踏步"""
    step = args.get("step", 20)
    
    try:
        _xgo_instance.mark_time(step)
        time.sleep(3)
        _xgo_instance.reset()
        return f"✓ 原地踏步({step}mm幅度)完成"
    except Exception as e:
        return f"❌ 原地踏步失败: {str(e)}"


def _execute_periodic_tran(args: Dict) -> str:
    """周期性平移"""
    axis = args.get("axis", "z")
    period = args.get("period", 2)
    wait_time = args.get("wait_time", 5)
    
    try:
        _xgo_instance.periodic_tran(axis, period)
        if wait_time > 0:
            time.sleep(wait_time)
            _xgo_instance.reset()
        direction = {"x": "前后", "y": "左右", "z": "上下"}.get(axis, axis)
        return f"✓ 周期性{direction}平移运动完成(周期{period}秒)"
    except Exception as e:
        return f"❌ 周期性平移失败: {str(e)}"


def _execute_periodic_rot(args: Dict) -> str:
    """周期性旋转"""
    axis = args.get("axis", "r")
    period = args.get("period", 2)
    wait_time = args.get("wait_time", 5)
    
    try:
        _xgo_instance.periodic_rot(axis, period)
        if wait_time > 0:
            time.sleep(wait_time)
            _xgo_instance.reset()
        direction = {"r": "Roll轴", "p": "Pitch轴", "y": "Yaw轴"}.get(axis, axis)
        return f"✓ 周期性{direction}摇摆运动完成(周期{period}秒)"
    except Exception as e:
        return f"❌ 周期性旋转失败: {str(e)}"


def _execute_gait_type(args: Dict) -> str:
    """设置步态类型"""
    mode = args.get("mode", "trot")
    
    try:
        mode_map = {
            "trot": "小跑步态",
            "walk": "行走步态",
            "high_walk": "高抬腿行走",
            "slow_trot": "慢速小跑"
        }
        
        if mode not in mode_map:
            return f"❌ 未知步态类型: {mode}, 支持: trot, walk, high_walk, slow_trot"
        
        _xgo_instance.gait_type(mode)
        time.sleep(0.5)
        return f"✓ 步态设置为{mode_map[mode]}"
    except Exception as e:
        return f"❌ 步态设置失败: {str(e)}"


def _execute_pace(args: Dict) -> str:
    """设置步伐频率"""
    mode = args.get("mode", "normal")
    
    try:
        mode_map = {
            "normal": "正常频率",
            "slow": "慢速频率",
            "high": "高速频率"
        }
        
        if mode not in mode_map:
            return f"❌ 未知频率模式: {mode}, 支持: normal, slow, high"
        
        _xgo_instance.pace(mode)
        time.sleep(0.5)
        return f"✓ 步伐频率设置为{mode_map[mode]}"
    except Exception as e:
        return f"❌ 频率设置失败: {str(e)}"


def _execute_imu(args: Dict) -> str:
    """IMU自稳开关"""
    mode = args.get("mode", 1)
    
    try:
        if mode not in [0, 1]:
            return "❌ 模式参数错误，必须为0(关闭)或1(开启)"
        
        _xgo_instance.imu(mode)
        time.sleep(0.3)
        status = "开启" if mode == 1 else "关闭"
        return f"✓ IMU自稳已{status}"
    except Exception as e:
        return f"❌ IMU设置失败: {str(e)}"


def _execute_leg(args: Dict) -> str:
    """单腿控制"""
    leg_id = args.get("leg_id", 1)
    x = args.get("x", 0)
    y = args.get("y", 0)
    z = args.get("z", 100)
    
    try:
        if leg_id not in [1, 2, 3, 4]:
            return "❌ 腿编号错误，必须为1-4 (1=左前, 2=右前, 3=右后, 4=左后)"
        
        _xgo_instance.leg(leg_id, [x, y, z])
        time.sleep(0.5)
        leg_names = {1: "左前腿", 2: "右前腿", 3: "右后腿", 4: "左后腿"}
        return f"✓ {leg_names[leg_id]}位置设置完成(X:{x}, Y:{y}, Z:{z})mm"
    except Exception as e:
        return f"❌ 单腿控制失败: {str(e)}"


def _execute_motor(args: Dict) -> str:
    """单舵机控制"""
    motor_id = args.get("motor_id", 11)
    angle = args.get("angle", 0)
    
    try:
        valid_ids = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51]
        if motor_id not in valid_ids:
            return f"❌ 舵机编号错误: {motor_id}, 有效范围: 11-13, 21-23, 31-33, 41-43, 51"
        
        _xgo_instance.motor(motor_id, angle)
        time.sleep(0.5)
        return f"✓ 舵机{motor_id}角度设置为{angle}°"
    except Exception as e:
        return f"❌ 舵机控制失败: {str(e)}"


def _execute_find_ball(args: Dict) -> str:
    """寻找小球"""
    color = args.get("color", "red")
    max_search_time = args.get("max_search_time", 30.0)
    
    if _xgo_edu is None:
        return "❌ 摄像头不可用"
    
    try:
        import cv2
        import numpy as np
        
        color_map = {
            'red': {'name': '红色', 'lower': [0, 43, 46], 'upper': [10, 255, 255]},
            'green': {'name': '绿色', 'lower': [35, 43, 46], 'upper': [77, 255, 255]},
            'blue': {'name': '蓝色', 'lower': [100, 43, 46], 'upper': [124, 255, 255]}
        }
        
        if color not in color_map:
            return f"❌ 不支持的颜色: {color}, 支持: red, green, blue"
        
        color_info = color_map[color]
        color_name = color_info['name']
        
        try:
            _xgo_edu.open_camera()
            time.sleep(1)
        except Exception as cam_e:
            return f"❌ 摄像头初始化失败: {str(cam_e)}"
        
        start_time = time.time()
        
        while time.time() - start_time < max_search_time:
            try:
                image = _xgo_edu.picam2.capture_array()
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, np.array(color_info['lower']), np.array(color_info['upper']))
                mask = cv2.erode(mask, None, iterations=2)
                mask = cv2.dilate(mask, None, iterations=2)
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if len(contours) > 0:
                    largest_contour = max(contours, key=cv2.contourArea)
                    ((x, y), radius) = cv2.minEnclosingCircle(largest_contour)
                    
                    if radius > 10:
                        distance_cm = int(320 * 2 / radius) if radius > 0 else 0
                        return f"✓ 找到{color_name}小球！位置:({int(x)}, {int(y)}), 半径:{int(radius)}, 距离:约{distance_cm}cm"
            except:
                pass
            time.sleep(0.1)
        
        return f"❓ 搜索超时，未找到{color_name}小球"
    except Exception as e:
        return f"❌ 小球搜索失败: {str(e)}"


def _execute_catch_ball(args: Dict) -> str:
    """识别并抓取指定颜色的小球（完整流程）"""
    color = args.get("color", "red")
    max_search_time = args.get("max_search_time", 30.0)
    max_grab_attempts = args.get("max_grab_attempts", 3)
    
    if _xgo_instance is None or _xgo_edu is None:
        return "❌ XGO机器人或教育库不可用"
    
    try:
        import cv2
        import numpy as np
        
        # 颜色映射
        color_map = {
            'red': '红色', 'r': '红色',
            'green': '绿色', 'g': '绿色',
            'blue': '蓝色', 'b': '蓝色'
        }
        
        color_lower = color.lower()
        if color_lower not in color_map:
            return f"❌ 不支持的颜色: {color}，支持: red, green, blue"
        
        color_name = color_map[color_lower]
        
        # HSV颜色范围
        color_ranges = {
            'red': {
                'lower1': np.array([0, 120, 60]),
                'upper1': np.array([15, 255, 255]),
                'lower2': np.array([160, 120, 60]),
                'upper2': np.array([180, 255, 255])
            },
            'blue': {
                'lower1': np.array([90, 100, 60]),
                'upper1': np.array([130, 255, 255]),
                'lower2': np.array([90, 100, 60]),
                'upper2': np.array([130, 255, 255])
            },
            'green': {
                'lower1': np.array([40, 80, 60]),
                'upper1': np.array([80, 255, 255]),
                'lower2': np.array([40, 80, 60]),
                'upper2': np.array([80, 255, 255])
            }
        }
        
        # 映射简写
        if color_lower in ['r', 'g', 'b']:
            color_lower = {'r': 'red', 'g': 'green', 'b': 'blue'}[color_lower]
        
        def detect_ball(frame, target_color):
            """检测特定颜色的小球"""
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            ranges = color_ranges[target_color]
            
            if target_color == 'red':
                mask1 = cv2.inRange(hsv, ranges['lower1'], ranges['upper1'])
                mask2 = cv2.inRange(hsv, ranges['lower2'], ranges['upper2'])
                mask = cv2.bitwise_or(mask1, mask2)
            else:
                mask = cv2.inRange(hsv, ranges['lower1'], ranges['upper1'])
            
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            masked = cv2.bitwise_and(frame, frame, mask=mask)
            gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (7, 7), 2)
            
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, dp=1, minDist=25,
                param1=40, param2=18, minRadius=10, maxRadius=80
            )
            
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                if len(circles) > 0:
                    max_circle = max(circles, key=lambda c: c[2])
                    return int(max_circle[0]), int(max_circle[1]), int(max_circle[2])
            
            return 0, 0, 0
        
        def calculate_distance(radius):
            if radius == 0:
                return float('inf')
            return 600 / radius
        
        def make_lie_down():
            _xgo_instance.translation('z', 75)
            _xgo_instance.attitude('p', 25)
            time.sleep(1)
        
        def check_grab_success():
            try:
                motor_angles = _xgo_instance.read_motor()
                if motor_angles and len(motor_angles) >= 15:
                    claw_angle = motor_angles[12]
                    return claw_angle > -60
                return False
            except:
                return False
        
        def attempt_catch():
            _xgo_instance.claw(0)
            time.sleep(0.5)
            _xgo_instance.arm_polar(226, 130)
            time.sleep(2)
            _xgo_instance.claw(245)
            time.sleep(1.5)
            
            success = check_grab_success()
            
            if success:
                _xgo_instance.arm_polar(90, 100)
                time.sleep(1)
                _xgo_instance.attitude('p', 10)
                time.sleep(1)
                return True
            else:
                _xgo_instance.claw(0)
                time.sleep(0.5)
                _xgo_instance.arm_polar(90, 100)
                time.sleep(1)
                return False
        
        # 显示任务开始
        try:
            _xgo_edu.lcd_clear()
            _xgo_edu.lcd_text(5, 5, f"Catch {color_name} ball", 14)
        except:
            pass
        
        # 趴下准备
        make_lie_down()
        
        # 初始化摄像头
        try:
            if _xgo_edu.picam2 is None:
                _xgo_edu.open_camera()
                time.sleep(2)
        except Exception as e:
            return f"❌ 摄像头初始化失败: {str(e)}"
        
        # 搜索小球
        start_time = time.time()
        search_attempts = 0
        max_search_attempts = 25
        found_ball = False
        
        while search_attempts < max_search_attempts and not found_ball:
            if max_search_time > 0 and (time.time() - start_time) > max_search_time:
                _xgo_instance.reset()
                return f"⏰ 搜索超时，未找到{color_name}小球"
            
            try:
                if _xgo_edu.picam2 is None:
                    _xgo_edu.open_camera()
                    time.sleep(1)
                
                if _xgo_edu.picam2 is not None:
                    frame = _xgo_edu.picam2.capture_array()
                    ball_x, ball_y, ball_radius = detect_ball(frame, color_lower)
                    
                    if ball_radius > 0:
                        distance = calculate_distance(ball_radius)
                        
                        if distance > 16.9:
                            _xgo_instance.move('x', 3)
                            time.sleep(1.2)
                            _xgo_instance.stop()
                        elif distance < 13:
                            _xgo_instance.move('x', -3)
                            time.sleep(0.8)
                            _xgo_instance.stop()
                        elif 13 <= distance <= 16.9:
                            center_x = 160
                            if abs(ball_x - center_x) > 20:
                                if ball_x > center_x:
                                    _xgo_instance.move('y', 3)
                                else:
                                    _xgo_instance.move('y', -3)
                                time.sleep(0.6)
                                _xgo_instance.stop()
                                continue
                            
                            found_ball = True
                            break
                    else:
                        if search_attempts % 4 == 3:
                            _xgo_instance.turn(60)
                            time.sleep(0.8)
                            _xgo_instance.stop()
                            time.sleep(0.5)
            except Exception as e:
                print(f"⚠️ 检测异常: {e}")
            
            search_attempts += 1
            time.sleep(0.6)
        
        # 尝试抓取
        grabbed_successfully = False
        grab_attempts = 0
        
        if found_ball:
            try:
                _xgo_edu.lcd_clear()
                _xgo_edu.lcd_text(5, 5, f"Grabbing {color_name}", 14)
            except:
                pass
            
            while grab_attempts < max_grab_attempts and not grabbed_successfully:
                grabbed_successfully = attempt_catch()
                grab_attempts += 1
                
                if not grabbed_successfully and grab_attempts < max_grab_attempts:
                    time.sleep(1)
        
        # 站起
        _xgo_instance.action(2)
        time.sleep(3)
        _xgo_instance.reset()
        
        # 清理摄像头
        try:
            if _xgo_edu.picam2 is not None:
                _xgo_edu.picam2.stop()
                _xgo_edu.picam2.close()
        except:
            pass
        
        total_time = int(time.time() - start_time)
        
        if grabbed_successfully:
            try:
                _xgo_edu.lcd_clear()
                _xgo_edu.lcd_text(5, 5, "Success!", 16)
            except:
                pass
            return f"✅ XGO成功抓取{color_name}小球！搜索次数:{search_attempts}, 抓取次数:{grab_attempts}, 耗时:{total_time}秒"
        else:
            try:
                _xgo_edu.lcd_clear()
                _xgo_edu.lcd_text(5, 5, "Failed", 16)
            except:
                pass
            
            if found_ball:
                return f"❌ 找到{color_name}小球但抓取失败，尝试{grab_attempts}次，耗时{total_time}秒"
            else:
                return f"❌ 未找到{color_name}小球，搜索{search_attempts}次，耗时{total_time}秒"
    
    except Exception as e:
        try:
            _xgo_instance.reset()
        except:
            pass
        return f"❌ 抓取异常: {str(e)}"


def _execute_display_picture(args: Dict) -> str:
    """显示本地图片"""
    filename = args.get("filename", "")
    x = args.get("x", 0)
    y = args.get("y", 0)
    
    if _xgo_edu is None:
        return "❌ 屏幕不可用"
    
    try:
        _xgo_edu.lcd_picture(filename, x, y)
        return f"🖼️ XGO屏幕显示图片: {filename} (位置: {x},{y})"
    except Exception as e:
        return f"❌ 显示图片失败: {str(e)}"


def _execute_speak(args: Dict) -> str:
    """播放本地音频"""
    filename = args.get("filename", "")
    
    try:
        os.system(f"mplayer {_XGO_MUSIC}/{filename}")
        return f"🔊 XGO播放音频: {filename}"
    except Exception as e:
        return f"❌ 播放音频失败: {str(e)}"


def _execute_play_http_audio(args: Dict) -> str:
    """播放网络HTTP音频"""
    url = args.get("url", "")
    
    try:
        import subprocess
        cmd = f'mplayer "{url}"'
        subprocess.run(cmd, shell=True, check=True)
        return f"✓ XGO音频播放完成: {url}"
    except Exception as e:
        return f"❌ 音频播放失败: {str(e)}"


def _execute_display_http_image(args: Dict) -> str:
    """显示网络HTTP图片"""
    url = args.get("url", "")
    x = args.get("x", 0)
    y = args.get("y", 0)
    
    if _xgo_edu is None:
        return "❌ 屏幕不可用"
    
    try:
        from PIL import Image
        from io import BytesIO
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        image = Image.open(BytesIO(response.content))
        image = image.resize((320, 240))
        
        _xgo_edu.splash.paste(image, (x, y))
        _xgo_edu.display.ShowImage(_xgo_edu.splash)
        
        return f"✓ XGO图片已显示: {url}"
    except Exception as e:
        return f"❌ 显示HTTP图片失败: {str(e)}"


def _execute_generate_and_display_image(args: Dict, api_key: str) -> str:
    """AI生成图片并显示"""
    prompt = args.get("prompt", "")
    size = args.get("size", "960*720")
    
    if not api_key:
        return "❌ 未提供API密钥，无法调用图片生成服务"
    
    if _xgo_edu is None:
        return "❌ 屏幕不可用"
    
    try:
        # 显示生成中状态
        try:
            _xgo_edu.lcd_clear()
            _xgo_edu.lcd_text(5, 5, "🎨 AI图片生成中...", 14)
        except:
            pass
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "wanx2.1-t2i-turbo",
            "input": {
                "prompt": prompt
            },
            "parameters": {
                "size": size,
                "n": 1
            }
        }
        
        # 提交生成任务
        response = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code != 200:
            return f"❌ API请求失败: {response.status_code}"
        
        result = response.json()
        
        if "output" not in result or "task_id" not in result["output"]:
            return "❌ API返回数据格式异常"
        
        task_id = result["output"]["task_id"]
        
        # 轮询任务状态
        for _ in range(60):
            time.sleep(2)
            
            status_response = requests.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
            
            if status_response.status_code != 200:
                continue
            
            status_result = status_response.json()
            task_status = status_result.get("output", {}).get("task_status", "")
            
            if task_status == "SUCCEEDED":
                results = status_result.get("output", {}).get("results", [])
                if results and "url" in results[0]:
                    image_url = results[0]["url"]
                    
                    # 显示图片
                    display_result = _execute_display_http_image({"url": image_url, "x": 0, "y": 0})
                    
                    return f"🎨 AI图片生成并显示完成\n提示词: {prompt}\n{display_result}"
                
                return "❌ 图片生成完成但未获取到URL"
            
            elif task_status == "FAILED":
                return f"❌ 图片生成失败: {status_result.get('output', {}).get('message', '未知错误')}"
        
        return "❌ 图片生成超时"
        
    except Exception as e:
        return f"❌ AI图片生成失败: {str(e)}"


def _execute_rider_reset_odom() -> str:
    """Rider重置里程计"""
    model = _model_type or 'xgomini'
    
    if model != 'xgorider':
        return "❌ 此功能仅支持Rider机型"
    
    try:
        _xgo_instance.rider_reset_odom()
        time.sleep(0.3)
        return "✓ Rider里程计已重置"
    except Exception as e:
        return f"❌ Rider里程计重置失败: {str(e)}"


def _execute_rider_calibration(args: Dict) -> str:
    """Rider校准"""
    state = args.get("state", "start")
    model = _model_type or 'xgomini'
    
    if model != 'xgorider':
        return "❌ 此功能仅支持Rider机型"
    
    try:
        if state not in ["start", "end"]:
            return "❌ 状态参数错误，必须为start或end"
        
        _xgo_instance.rider_calibration(state)
        time.sleep(0.5)
        
        status = "开始" if state == "start" else "结束"
        return f"✓ Rider校准{status}"
    except Exception as e:
        return f"❌ Rider校准失败: {str(e)}"


# =============================================================
# VoiceChatToolExecutor - 供 voice_chat.py 使用的工具执行器
# =============================================================

class VoiceChatToolExecutor:
    """
    voice_chat.py 专用工具执行器
    
    使用方法:
        executor = VoiceChatToolExecutor(api_key)
        tools = executor.get_tools()
        result = executor.execute("xgo_move", {"direction": "forward"})
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        _init_xgo()
    
    def get_tools(self) -> List[Dict]:
        """获取工具定义列表（OpenAI Function Call 格式）"""
        return get_tool_definitions()
    
    def execute(self, tool_name: str, arguments: Dict) -> str:
        """执行工具"""
        return execute_tool(tool_name, arguments, self.api_key)
    
    @property
    def model_type(self) -> str:
        """当前机型"""
        return get_model_type()
    
    @property
    def is_available(self) -> bool:
        """硬件是否可用"""
        return is_hardware_available()
