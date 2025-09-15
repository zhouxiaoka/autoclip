"""
统一的进度频道命名规范
避免频道名称不一致导致的消息丢失问题
"""

def project_progress_channel(project_id: str) -> str:
    """
    生成项目进度频道名称
    
    Args:
        project_id: 项目ID
        
    Returns:
        统一的频道名称: progress:project:<project_id>
    """
    # 统一用冒号分隔，去掉重复"project_"
    return f"progress:project:{project_id}"

def task_progress_channel(task_id: str) -> str:
    """
    生成任务进度频道名称
    
    Args:
        task_id: 任务ID
        
    Returns:
        统一的频道名称: progress:task:<task_id>
    """
    return f"progress:task:{task_id}"

def normalize_channel(raw: str) -> str:
    """
    规范化频道名称，统一格式
    
    Args:
        raw: 原始频道名
        
    Returns:
        规范化的频道名称
    """
    if not raw:
        return ""
    
    s = raw.strip()
    
    # 如果是项目ID格式，转换为项目进度频道
    if s.startswith("progress:project:"):
        return s
    elif s.startswith("project_"):
        # 去掉project_前缀，提取纯ID
        project_id = s[8:]  # 去掉"project_"前缀
        return project_progress_channel(project_id)
    elif s.startswith("progress:project_"):
        # 处理progress:project_<id>格式
        project_id = s[17:]  # 去掉"progress:project_"前缀
        return project_progress_channel(project_id)
    else:
        # 假设是纯项目ID
        return project_progress_channel(s)
