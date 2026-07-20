"""
EPG管理器 - 增强版
支持多格式、多源、双缓冲、智能更新
"""
import os
import time
import json
import gzip
import threading
import requests
from datetime import datetime, timedelta
from bisect import bisect_right
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from xml.etree.ElementTree import iterparse
import re

# ---------- 数据结构 ----------
@dataclass
class EpgProgram:
    __slots__ = ['start_ts', 'end_ts', 'title', 'desc', 'channel_id']
    start_ts: int
    end_ts: int
    title: str
    desc: str
    channel_id: str

class EpgDataPool:
    __slots__ = ['channel_map', 'data_timestamp', 'program_count', 'source_info']
    def __init__(self):
        self.channel_map: Dict[str, List[EpgProgram]] = {}
        self.data_timestamp: int = 0
        self.program_count: int = 0
        self.source_info: Dict[str, Any] = {}  # 记录每个源的更新时间等

# ---------- 主管理器 ----------
class EpgManager:
    def __init__(self, cache_dir='epg_cache'):
        self._current_pool = EpgDataPool()
        self._update_lock = threading.RLock()
        self._is_updating = False
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # 配置参数
        self.days_before = 1    # 保留昨天
        self.days_after = 7     # 未来7天
        self.user_agent = 'KU9Player/2.0'
        self.timeout = 30
        
        # 加载磁盘缓存
        self._load_cache()
    
    # ---------- 公开接口 ----------
    def check_and_update(self, sources: List[Dict], callback: Optional[Callable]=None):
        """
        检查并更新EPG
        sources: [{'url': '...', 'type': 'xmltv|diyp|baichuan', 'priority': 1}]
        """
        if not sources or self._is_updating:
            return
        
        # 获取最新时间戳
        latest_ts = self._get_remote_timestamp(sources)
        if latest_ts <= self._current_pool.data_timestamp:
            if callback: callback(True, self._current_pool.program_count)
            return
        
        threading.Thread(target=self._do_update, args=(sources, callback), daemon=True).start()
    
    def get_current_program(self, channel_id: str, timestamp: int=None) -> Optional[EpgProgram]:
        """获取当前节目"""
        if timestamp is None:
            timestamp = int(time.time())
        pool = self._current_pool
        programs = pool.channel_map.get(channel_id, [])
        idx = bisect_right(programs, timestamp, key=lambda x: x.start_ts) - 1
        if idx >= 0 and programs[idx].start_ts <= timestamp < programs[idx].end_ts:
            return programs[idx]
        return None
    
    def get_programs(self, channel_id: str, start_ts: int, end_ts: int) -> List[EpgProgram]:
        """获取时间范围节目"""
        pool = self._current_pool
        programs = pool.channel_map.get(channel_id, [])
        # 二分查找起始
        left = bisect_right(programs, start_ts, key=lambda x: x.start_ts) - 1
        if left < 0: left = 0
        result = []
        for p in programs[left:]:
            if p.start_ts > end_ts:
                break
            if p.end_ts >= start_ts:
                result.append(p)
        return result
    
    def get_pool_stats(self) -> dict:
        pool = self._current_pool
        return {
            'program_count': pool.program_count,
            'channel_count': len(pool.channel_map),
            'timestamp': pool.data_timestamp,
            'is_updating': self._is_updating
        }
    
    # ---------- 内部更新逻辑 ----------
    def _do_update(self, sources, callback):
        with self._update_lock:
            if self._is_updating: return
            self._is_updating = True
        
        try:
            new_pool = EpgDataPool()
            new_pool.data_timestamp = self._get_remote_timestamp(sources)
            
            # 按优先级排序
            sorted_sources = sorted(sources, key=lambda x: x.get('priority', 0), reverse=True)
            
            for src in sorted_sources:
                url = src.get('url')
                fmt = src.get('type', 'auto')
                # 自动探测格式
                if fmt == 'auto':
                    fmt = self._detect_format(url)
                # 解析
                if fmt == 'xmltv':
                    self._parse_xmltv(url, new_pool)
                elif fmt == 'diyp':
                    self._parse_diyp(url, new_pool)
                elif fmt == 'baichuan':
                    self._parse_baichuan(url, new_pool)
                else:
                    # 尝试通用解析
                    self._parse_generic(url, new_pool)
            
            # 校验
            if new_pool.program_count > 0:
                self._current_pool = new_pool
                # 保存到磁盘
                self._save_cache()
                if callback: callback(True, new_pool.program_count)
            else:
                if callback: callback(False, 0)
        except Exception as e:
            print(f'[EPG] Update error: {e}')
            if callback: callback(False, 0)
        finally:
            self._is_updating = False
    
    # ---------- 格式解析器 ----------
    def _parse_xmltv(self, url, pool):
        """解析XMLTV格式 (标准xmltv)"""
        now = int(time.time())
        cutoff_start = now - self.days_before * 86400
        cutoff_end = now + self.days_after * 86400
        
        try:
            resp = requests.get(url, headers={'User-Agent': self.user_agent}, stream=True, timeout=self.timeout)
            resp.encoding = 'utf-8'
            # 使用iterparse流式解析
            for event, elem in iterparse(resp.raw, events=('end',), tag='programme'):
                try:
                    start = elem.get('start')
                    stop = elem.get('stop')
                    if not start or not stop:
                        elem.clear(); continue
                    start_ts = self._xmltv_time_to_ts(start)
                    end_ts = self._xmltv_time_to_ts(stop)
                    if start_ts < cutoff_start or start_ts > cutoff_end:
                        elem.clear(); continue
                    channel = elem.get('channel', '')
                    if not channel:
                        elem.clear(); continue
                    title_elem = elem.find('title')
                    title = title_elem.text if title_elem is not None else '未知节目'
                    desc_elem = elem.find('desc')
                    desc = desc_elem.text if desc_elem is not None else ''
                    prog = EpgProgram(start_ts, end_ts, title.strip(), desc.strip(), channel)
                    if channel not in pool.channel_map:
                        pool.channel_map[channel] = []
                    pool.channel_map[channel].append(prog)
                    pool.program_count += 1
                except:
                    pass
                finally:
                    elem.clear()
        except Exception as e:
            print(f'[EPG] XMLTV parse error: {e}')
    
    def _parse_diyp(self, url, pool):
        """解析DIYP格式 (通常为json)"""
        try:
            resp = requests.get(url, timeout=self.timeout)
            data = resp.json()
            # DIYP格式: {'epg_data': {'channel_id': [{'start': 'HH:MM', 'end': 'HH:MM', 'title': '...'}]}}
            # 需要结合日期，通常频道数据按天提供
            # 这里简化：假设数据包含日期信息
            epg_data = data.get('epg_data', {})
            today = datetime.now().date()
            for ch_id, programs in epg_data.items():
                if ch_id not in pool.channel_map:
                    pool.channel_map[ch_id] = []
                for prog in programs:
                    start_str = prog.get('start')
                    end_str = prog.get('end')
                    title = prog.get('title', '')
                    # 构造当天的时间戳
                    start_dt = datetime.combine(today, datetime.strptime(start_str, '%H:%M').time())
                    end_dt = datetime.combine(today, datetime.strptime(end_str, '%H:%M').time())
                    # 处理跨天
                    if end_dt < start_dt:
                        end_dt += timedelta(days=1)
                    start_ts = int(start_dt.timestamp())
                    end_ts = int(end_dt.timestamp())
                    # 只保留近期
                    if start_ts > int(time.time()) - 86400 and start_ts < int(time.time()) + 7*86400:
                        ep = EpgProgram(start_ts, end_ts, title, '', ch_id)
                        pool.channel_map[ch_id].append(ep)
                        pool.program_count += 1
        except Exception as e:
            print(f'[EPG] DIYP parse error: {e}')
    
    def _parse_baichuan(self, url, pool):
        """解析百川格式 (类似xml但不同)"""
        # 百川通常也是xml，但标签不同，这里暂用xml解析适配
        # 实际可针对性处理，也可转为xmltv
        self._parse_xmltv(url, pool)  # 暂用相同解析
    
    def _parse_generic(self, url, pool):
        """通用尝试：先按xmltv，再按json"""
        try:
            self._parse_xmltv(url, pool)
        except:
            try:
                self._parse_diyp(url, pool)
            except:
                pass
    
    def _detect_format(self, url):
        """根据URL后缀或内容探测格式"""
        if url.endswith('.xml') or 'xmltv' in url:
            return 'xmltv'
        if url.endswith('.json') or 'diyp' in url:
            return 'diyp'
        if 'baichuan' in url:
            return 'baichuan'
        return 'xmltv'  # 默认
    
    # ---------- 辅助函数 ----------
    def _xmltv_time_to_ts(self, time_str):
        """xmltv时间转时间戳"""
        try:
            # 格式: 20240101120000 +0000
            if len(time_str) >= 14:
                year = int(time_str[0:4]); month = int(time_str[4:6]); day = int(time_str[6:8])
                hour = int(time_str[8:10]); minute = int(time_str[10:12]); second = int(time_str[12:14])
                dt = datetime(year, month, day, hour, minute, second)
                return int(dt.timestamp())
        except:
            pass
        return 0
    
    def _get_remote_timestamp(self, sources):
        """获取所有源的最新时间戳"""
        max_ts = 0
        for src in sources:
            url = src.get('url')
            try:
                head = requests.head(url, timeout=10)
                last_modified = head.headers.get('Last-Modified')
                if last_modified:
                    from email.utils import parsedate_to_datetime
                    ts = int(parsedate_to_datetime(last_modified).timestamp())
                    max_ts = max(max_ts, ts)
            except:
                pass
        # 若无法获取，使用当前时间
        if max_ts == 0:
            max_ts = int(time.time())
        return max_ts
    
    # ---------- 磁盘缓存 ----------
    def _save_cache(self):
        """将当前数据池保存到磁盘（压缩存储）"""
        pool = self._current_pool
        if pool.program_count == 0:
            return
        # 序列化为紧凑格式
        data = {
            'timestamp': pool.data_timestamp,
            'programs': {}
        }
        for ch_id, progs in pool.channel_map.items():
            data['programs'][ch_id] = [
                (p.start_ts, p.end_ts, p.title, p.desc) for p in progs
            ]
        # 压缩保存
        cache_file = os.path.join(self.cache_dir, 'epg_cache.json.gz')
        with gzip.open(cache_file, 'wt', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _load_cache(self):
        """从磁盘加载缓存"""
        cache_file = os.path.join(self.cache_dir, 'epg_cache.json.gz')
        if not os.path.exists(cache_file):
            return
        try:
            with gzip.open(cache_file, 'rt', encoding='utf-8') as f:
                data = json.load(f)
            pool = EpgDataPool()
            pool.data_timestamp = data.get('timestamp', 0)
            for ch_id, prog_list in data.get('programs', {}).items():
                programs = []
                for item in prog_list:
                    start_ts, end_ts, title, desc = item
                    programs.append(EpgProgram(start_ts, end_ts, title, desc, ch_id))
                pool.channel_map[ch_id] = programs
                pool.program_count += len(programs)
            self._current_pool = pool
        except Exception as e:
            print(f'[EPG] Load cache error: {e}')
