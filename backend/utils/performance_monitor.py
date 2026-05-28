"""
性能监控工具
监控系统性能指标，包括CPU、内存、磁盘、网络等
"""

import psutil
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import threading
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    PROCESS = "process"
    CUSTOM = "custom"


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    metric_type: MetricType
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SystemStats:
    """系统统计信息"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_total: int
    disk_usage_percent: float
    disk_used: int
    disk_total: int
    network_bytes_sent: int
    network_bytes_recv: int
    active_processes: int


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history_size: int = 1000, collection_interval: int = 60):
        self.max_history_size = max_history_size
        self.collection_interval = collection_interval
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.system_stats_history: deque = deque(maxlen=max_history_size)
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.lock = threading.Lock()
        
        # 网络统计基准
        self._network_baseline = None
        self._last_network_check = None
    
    def _get_system_stats(self) -> SystemStats:
        """获取系统统计信息"""
        
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used
        memory_total = memory.total
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        disk_usage_percent = (disk.used / disk.total) * 100
        disk_used = disk.used
        disk_total = disk.total
        
        # 网络统计
        network = psutil.net_io_counters()
        network_bytes_sent = network.bytes_sent
        network_bytes_recv = network.bytes_recv
        
        # 活跃进程数
        active_processes = len(psutil.pids())
        
        return SystemStats(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used=memory_used,
            memory_total=memory_total,
            disk_usage_percent=disk_usage_percent,
            disk_used=disk_used,
            disk_total=disk_total,
            network_bytes_sent=network_bytes_sent,
            network_bytes_recv=network_bytes_recv,
            active_processes=active_processes
        )
    
    def _get_process_stats(self, process_name: str = None) -> List[Dict[str, Any]]:
        """获取进程统计信息"""
        
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
            try:
                if process_name and process_name not in proc.info['name']:
                    continue
                
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu_percent': proc.info['cpu_percent'],
                    'memory_percent': proc.info['memory_percent'],
                    'memory_rss': proc.info['memory_info'].rss if proc.info['memory_info'] else 0,
                    'memory_vms': proc.info['memory_info'].vms if proc.info['memory_info'] else 0
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return processes
    
    def _calculate_network_delta(self, current_stats: SystemStats) -> Dict[str, int]:
        """计算网络流量增量"""
        
        if self._network_baseline is None:
            self._network_baseline = current_stats
            self._last_network_check = current_stats.timestamp
            return {'bytes_sent_delta': 0, 'bytes_recv_delta': 0}
        
        time_delta = (current_stats.timestamp - self._last_network_check).total_seconds()
        if time_delta <= 0:
            return {'bytes_sent_delta': 0, 'bytes_recv_delta': 0}
        
        bytes_sent_delta = current_stats.network_bytes_sent - self._network_baseline.network_bytes_sent
        bytes_recv_delta = current_stats.network_bytes_recv - self._network_baseline.network_bytes_recv
        
        # 计算每秒流量
        bytes_sent_per_sec = bytes_sent_delta / time_delta
        bytes_recv_per_sec = bytes_recv_delta / time_delta
        
        self._network_baseline = current_stats
        self._last_network_check = current_stats.timestamp
        
        return {
            'bytes_sent_delta': bytes_sent_delta,
            'bytes_recv_delta': bytes_recv_delta,
            'bytes_sent_per_sec': bytes_sent_per_sec,
            'bytes_recv_per_sec': bytes_recv_per_sec
        }
    
    async def collect_metrics(self):
        """收集性能指标"""
        
        try:
            # 获取系统统计信息
            system_stats = self._get_system_stats()
            
            with self.lock:
                self.system_stats_history.append(system_stats)
            
            # 计算网络流量增量
            network_delta = self._calculate_network_delta(system_stats)
            
            # 创建性能指标
            metrics = [
                PerformanceMetric(
                    name="cpu_usage",
                    value=system_stats.cpu_percent,
                    unit="percent",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.CPU
                ),
                PerformanceMetric(
                    name="memory_usage",
                    value=system_stats.memory_percent,
                    unit="percent",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.MEMORY
                ),
                PerformanceMetric(
                    name="memory_used",
                    value=system_stats.memory_used,
                    unit="bytes",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.MEMORY
                ),
                PerformanceMetric(
                    name="disk_usage",
                    value=system_stats.disk_usage_percent,
                    unit="percent",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.DISK
                ),
                PerformanceMetric(
                    name="disk_used",
                    value=system_stats.disk_used,
                    unit="bytes",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.DISK
                ),
                PerformanceMetric(
                    name="network_sent_per_sec",
                    value=network_delta.get('bytes_sent_per_sec', 0),
                    unit="bytes_per_second",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.NETWORK
                ),
                PerformanceMetric(
                    name="network_recv_per_sec",
                    value=network_delta.get('bytes_recv_per_sec', 0),
                    unit="bytes_per_second",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.NETWORK
                ),
                PerformanceMetric(
                    name="active_processes",
                    value=system_stats.active_processes,
                    unit="count",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.PROCESS
                )
            ]
            
            with self.lock:
                self.metrics_history.extend(metrics)
            
            logger.debug(f"收集性能指标: {len(metrics)} 个指标")
            
        except Exception as e:
            logger.error(f"收集性能指标失败: {e}")
    
    async def start_monitoring(self):
        """开始监控"""
        
        if self.is_monitoring:
            logger.warning("性能监控已在运行")
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"开始性能监控，收集间隔: {self.collection_interval} 秒")
    
    async def stop_monitoring(self):
        """停止监控"""
        
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("停止性能监控")
    
    async def _monitoring_loop(self):
        """监控循环"""
        
        while self.is_monitoring:
            try:
                await self.collect_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(self.collection_interval)
    
    def get_current_stats(self) -> SystemStats:
        """获取当前系统统计信息"""
        
        with self.lock:
            if self.system_stats_history:
                return self.system_stats_history[-1]
            else:
                return self._get_system_stats()
    
    def get_metrics_summary(self, time_range_minutes: int = 60) -> Dict[str, Any]:
        """获取指标摘要"""
        
        cutoff_time = datetime.now() - timedelta(minutes=time_range_minutes)
        
        with self.lock:
            # 过滤时间范围内的指标
            recent_metrics = [
                metric for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]
            
            # 按指标名称分组
            metrics_by_name = {}
            for metric in recent_metrics:
                if metric.name not in metrics_by_name:
                    metrics_by_name[metric.name] = []
                metrics_by_name[metric.name].append(metric.value)
            
            # 计算统计信息
            summary = {}
            for name, values in metrics_by_name.items():
                if values:
                    summary[name] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values),
                        'latest': values[-1]
                    }
            
            return summary
    
    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        
        current_stats = self.get_current_stats()
        
        # 健康状态评估
        health_status = "healthy"
        warnings = []
        
        if current_stats.cpu_percent > 80:
            health_status = "warning"
            warnings.append(f"CPU使用率过高: {current_stats.cpu_percent:.1f}%")
        
        if current_stats.memory_percent > 85:
            health_status = "warning"
            warnings.append(f"内存使用率过高: {current_stats.memory_percent:.1f}%")
        
        if current_stats.disk_usage_percent > 90:
            health_status = "critical"
            warnings.append(f"磁盘使用率过高: {current_stats.disk_usage_percent:.1f}%")
        
        return {
            "status": health_status,
            "warnings": warnings,
            "current_stats": {
                "cpu_percent": current_stats.cpu_percent,
                "memory_percent": current_stats.memory_percent,
                "disk_usage_percent": current_stats.disk_usage_percent,
                "active_processes": current_stats.active_processes
            },
            "timestamp": current_stats.timestamp.isoformat()
        }
    
    def get_top_processes(self, limit: int = 10, sort_by: str = "cpu") -> List[Dict[str, Any]]:
        """获取占用资源最多的进程"""
        
        processes = self._get_process_stats()
        
        # 按指定字段排序
        if sort_by == "cpu":
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        elif sort_by == "memory":
            processes.sort(key=lambda x: x['memory_percent'], reverse=True)
        
        return processes[:limit]
    
    def add_custom_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """添加自定义指标"""
        
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            metric_type=MetricType.CUSTOM,
            tags=tags or {}
        )
        
        with self.lock:
            self.metrics_history.append(metric)
    
    def clear_history(self):
        """清空历史数据"""
        
        with self.lock:
            self.metrics_history.clear()
            self.system_stats_history.clear()
        
        logger.info("清空性能监控历史数据")


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()


# 性能监控装饰器
def monitor_performance(metric_name: str, unit: str = ""):
    """性能监控装饰器"""
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_execution_time",
                    execution_time,
                    unit or "seconds"
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_error_time",
                    execution_time,
                    unit or "seconds",
                    {"error": str(e)}
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_execution_time",
                    execution_time,
                    unit or "seconds"
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_error_time",
                    execution_time,
                    unit or "seconds",
                    {"error": str(e)}
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
