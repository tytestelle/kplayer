import json
import re
from typing import List, Dict, Optional

class Channel:
    __slots__ = ['name', 'url', 'tvg_id', 'tvg_logo', 'group', 'epg_channel_id', 'user_agent', 'headers']
    def __init__(self, name='', url='', tvg_id='', tvg_logo='', group='默认', epg_channel_id=None):
        self.name = name
        self.url = url
        self.tvg_id = tvg_id
        self.tvg_logo = tvg_logo
        self.group = group
        self.epg_channel_id = epg_channel_id or tvg_id
        self.user_agent = ''
        self.headers = {}

class ChannelManager:
    def __init__(self):
        self.channels: List[Channel] = []
        self.groups: Dict[str, List[int]] = {}  # group_name -> indices
        self.favorites: set = set()
        self.current_index = -1
    
    def load_from_m3u(self, content: str):
        """解析M3U"""
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                # 解析属性
                attrs = self._parse_extinf(line)
                name = attrs.get('name', '未知')
                tvg_id = attrs.get('tvg-id', '')
                tvg_logo = attrs.get('tvg-logo', '')
                group = attrs.get('group-title', '默认')
                if i+1 < len(lines):
                    url = lines[i+1].strip()
                    if url and not url.startswith('#'):
                        ch = Channel(name, url, tvg_id, tvg_logo, group)
                        self._add_channel(ch)
                        i += 1
            i += 1
    
    def load_from_txt(self, content: str):
        """解析TXT格式（频道名,url）"""
        for line in content.splitlines():
            if ',' in line:
                parts = line.split(',', 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith('http'):
                    ch = Channel(name, url, '', '', '默认')
                    self._add_channel(ch)
    
    def load_from_json(self, data: list):
        """从JSON列表加载"""
        for item in data:
            ch = Channel(
                name=item.get('name', ''),
                url=item.get('url', ''),
                tvg_id=item.get('tvg_id', ''),
                tvg_logo=item.get('tvg_logo', ''),
                group=item.get('group', '默认')
            )
            ch.headers = item.get('headers', {})
            ch.user_agent = item.get('user_agent', '')
            self._add_channel(ch)
    
    def _add_channel(self, ch: Channel):
        idx = len(self.channels)
        self.channels.append(ch)
        if ch.group not in self.groups:
            self.groups[ch.group] = []
        self.groups[ch.group].append(idx)
    
    def search(self, keyword: str) -> List[int]:
        """搜索频道（不区分大小写）"""
        keyword = keyword.lower()
        result = []
        for i, ch in enumerate(self.channels):
            if keyword in ch.name.lower() or keyword in ch.tvg_id.lower():
                result.append(i)
        return result
    
    def toggle_favorite(self, index: int):
        if index in self.favorites:
            self.favorites.remove(index)
        else:
            self.favorites.add(index)
    
    def export_json(self) -> list:
        return [{
            'name': ch.name,
            'url': ch.url,
            'tvg_id': ch.tvg_id,
            'tvg_logo': ch.tvg_logo,
            'group': ch.group,
            'headers': ch.headers,
            'user_agent': ch.user_agent
        } for ch in self.channels]
