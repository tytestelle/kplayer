"""
EPG管理器
- 支持多个EPG数据源
- 双缓冲原子切换（更新时保留旧数据）
- 流式解析，内存友好
- 自动过滤过期数据
"""
import time
import threading
import requests
from datetime import datetime, timedelta
from bisect import bisect_right
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from xml.etree.ElementTree import iterparse


@dataclass
class EpgProgram:
    """EPG节目数据（使用__slots__节省内存）"""
    __slots__ = ['start_ts', 'end_ts', 'title', 'desc', 'channel_id']
    start_ts: int
    end_ts: int
    title: str
    desc: str
    channel_id: str


class EPGDataPool:
    """EPG数据池（双缓冲中的一个缓冲）"""
    __slots__ = ['channel_map', 'data_timestamp', 'program_count']
    
    def __init__(self):
        self.channel_map: Dict[str, List[EpgProgram]] = {}
        self.data_timestamp: int = 0
        self.program_count: int = 0


class EPGManager:
    """EPG管理器 - 双缓冲原子切换"""
    
    def __init__(self):
        # 当前有效数据（所有读取操作访问此指针）
        self._current_pool = EPGDataPool()
        # 更新锁，防止并发更新
        self._update_lock = threading.Lock()
        self._is_updating = False
        # 默认缓存天数（只保留昨天+未来3天）
        self.cache_days_before = 1
        self.cache_days_after = 3
        # 用户代理
        self.user_agent = 'KU9Player/1.0'
    
    def check_and_update(self, sources: List[str], callback: Optional[Callable] = None):
        """
        检查并更新EPG
        如果有更新，在后台下载并解析，完成后原子切换
        """
        if not sources:
            return
        
        # 如果正在更新，跳过
        if self._is_updating:
            return
        
        # 快速检查：获取远程时间戳
        latest_ts = self._fetch_latest_timestamp(sources)
        if latest_ts <= self._current_pool.data_timestamp:
            # 没有更新
            if callback:
                callback(True, self._current_pool.program_count)
            return
        
        # 启动后台更新线程
        threading.Thread(
            target=self._perform_update,
            args=(sources, callback),
            daemon=True
        ).start()
    
    def _perform_update(self, sources: List[str], callback: Optional[Callable]):
        """执行后台更新（在独立线程中运行）"""
        with self._update_lock:
            if self._is_updating:
                return
            self._is_updating = True
        
        try:
            # 构建新数据池（在局部变量中构建，不影响现有数据）
            new_pool = EPGDataPool()
            new_pool.data_timestamp = self._fetch_latest_timestamp(sources)
            
            # 流式解析每个数据源
            for source in sources:
                self._stream_parse_epg(source, new_pool)
            
            # 校验数据完整性
            if new_pool.program_count > 0:
                # ⭐ 原子切换：Python中赋值是原子操作
                self._current_pool = new_pool
                print(f'[EPG] 更新成功，节目数: {new_pool.program_count}')
                if callback:
                    callback(True, new_pool.program_count)
            else:
                print('[EPG] 新数据为空，保留旧数据')
                if callback:
                    callback(False, 0)
                    
        except Exception as e:
            print(f'[EPG] 更新异常: {e}，保留旧数据')
            if callback:
                callback(False, 0)
        finally:
            self._is_updating = False
    
    def _stream_parse_epg(self, source_url: str, pool: EPGDataPool):
        """
        流式解析EPG（xmltv格式）
        使用iterparse，边下载边解析，内存占用恒定
        """
        # 计算时间窗口
        now = int(time.time())
        cutoff_start = now - self.cache_days_before * 86400
        cutoff_end = now + self.cache_days_after * 86400
        
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(source_url, headers=headers, stream=True, timeout=60)
            response.encoding = 'utf-8'
            
            # 使用iterparse流式解析，不构建完整DOM
            for event, elem in iterparse(response.raw, events=('end',), tag='programme'):
                try:
                    # 解析时间
                    start_str = elem.get('start', '')
                    end_str = elem.get('stop', '')
                    
                    start_ts = self._xmltv_time_to_ts(start_str)
                    end_ts = self._xmltv_time_to_ts(end_str)
                    
                    # 过滤：只保留时间窗口内的数据
                    if start_ts < cutoff_start or start_ts > cutoff_end:
                        elem.clear()
                        continue
                    
                    # 解析频道ID
                    channel_id = elem.get('channel', '')
                    if not channel_id:
                        elem.clear()
                        continue
                    
                    # 解析标题
                    title_elem = elem.find('title')
                    title = title_elem.text if title_elem is not None else '未知节目'
                    title = (title or '未知节目').strip()
                    
                    # 解析描述
                    desc_elem = elem.find('desc')
                    desc = desc_elem.text if desc_elem is not None else ''
                    desc = (desc or '').strip()
                    
                    # 创建节目对象
                    prog = EpgProgram(
                        start_ts=start_ts,
                        end_ts=end_ts,
                        title=title,
                        desc=desc,
                        channel_id=channel_id
                    )
                    
                    # 存入数据池
                    if channel_id not in pool.channel_map:
                        pool.channel_map[channel_id] = []
                    pool.channel_map[channel_id].append(prog)
                    pool.program_count += 1
                    
                except Exception as e:
                    # 单条数据损坏，跳过不影响整体
                    pass
                finally:
                    # 立即释放元素内存
                    elem.clear()
            
        except Exception as e:
            print(f'[EPG] 解析源 {source_url} 失败: {e}')
            raise
    
    def _xmltv_time_to_ts(self, time_str: str) -> int:
        """将xmltv时间格式转为Unix时间戳"""
        if not time_str:
            return 0
        try:
            # 格式: 20240101120000 +0000
            # 或: 20240101120000
            time_str = time_str.strip()
            if len(time_str) >= 14:
                year = int(time_str[0:4])
                month = int(time_str[4:6])
                day = int(time_str[6:8])
                hour = int(time_str[8:10])
                minute = int(time_str[10:12])
                second = int(time_str[12:14])
                
                dt = datetime(year, month, day, hour, minute, second)
                return int(dt.timestamp())
        except:
            pass
        return 0
    
    def _fetch_latest_timestamp(self, sources: List[str]) -> int:
        """获取远端EPG的最新时间戳（HEAD请求）"""
        max_ts = 0
        for source in sources:
            try:
                headers = {'User-Agent': self.user_agent}
                response = requests.head(source, headers=headers, timeout=10)
                last_modified = response.headers.get('Last-Modified', '')
                if last_modified:
                    # 解析HTTP日期
                    from email.utils import parsedate_to_datetime
                    ts = int(parsedate_to_datetime(last_modified).timestamp())
                    max_ts = max(max_ts, ts)
            except:
                # HEAD失败，使用当前时间作为fallback
                max_ts = max(max_ts, int(time.time()))
        return max_ts or int(time.time())
    
    def get_current_program(self, channel_id: str, current_ts: int = None) -> Optional[EpgProgram]:
        """
        获取指定频道当前播放的节目
        使用二分查找，O(log n)
        """
        if current_ts is None:
            current_ts = int(time.time())
        
        pool = self._current_pool  # 原子读取
        programs = pool.channel_map.get(channel_id, [])
        
        if not programs:
            return None
        
        # 二分查找
        idx = bisect_right(programs, current_ts, key=lambda x: x.start_ts) - 1
        
        if idx >= 0 and idx < len(programs):
            prog = programs[idx]
            if prog.start_ts <= current_ts < prog.end_ts:
                return prog
        
        return None
    
    def get_programs(self, channel_id: str, start_ts: int, end_ts: int) -> List[EpgProgram]:
        """获取指定频道在时间范围内的节目列表"""
        pool = self._current_pool
        programs = pool.channel_map.get(channel_id, [])
        
        result = []
        for prog in programs:
            if prog.start_ts >= start_ts and prog.end_ts <= end_ts:
                result.append(prog)
            if prog.start_ts > end_ts:
                break
        return result
    
    def get_pool_stats(self) -> dict:
        """获取数据池统计信息"""
        pool = self._current_pool
        return {
            'program_count': pool.program_count,
            'channel_count': len(pool.channel_map),
            'timestamp': pool.data_timestamp,
            'is_updating': self._is_updating
        }
