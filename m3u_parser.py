"""
M3U播放列表解析器
支持标准M3U和扩展M3U格式
支持提取 tvg-id, tvg-name, tvg-logo, group-title 等属性
"""
import re
import requests
from urllib.parse import urlparse
from typing import List, Dict, Optional


class M3UParser:
    """M3U解析器"""
    
    def __init__(self):
        self.user_agent = 'KU9Player/1.0'
    
    def parse_url(self, url: str) -> List[Dict]:
        """从URL解析M3U"""
        headers = {'User-Agent': self.user_agent}
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        return self.parse_content(response.text)
    
    def parse_file(self, filepath: str) -> List[Dict]:
        """从本地文件解析M3U"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return self.parse_content(f.read())
    
    def parse_content(self, content: str) -> List[Dict]:
        """解析M3U内容"""
        channels = []
        lines = content.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 跳过空行和注释（非EXTINF）
            if not line or line.startswith('#'):
                # 如果是EXTINF行，解析频道信息
                if line.startswith('#EXTINF:'):
                    channel = self._parse_extinf(line)
                    
                    # 下一行是URL
                    if i + 1 < len(lines):
                        url = lines[i + 1].strip()
                        if url and not url.startswith('#'):
                            channel['url'] = url
                            channels.append(channel)
                            i += 1  # 跳过URL行
                i += 1
            else:
                # 没有EXTINF的裸URL
                if self._is_valid_url(line):
                    channels.append({
                        'name': self._extract_name_from_url(line),
                        'url': line,
                        'tvg_id': '',
                        'tvg_name': '',
                        'tvg_logo': '',
                        'group': '默认'
                    })
                i += 1
        
        return channels
    
    def _parse_extinf(self, line: str) -> Dict:
        """解析EXTINF行"""
        # 提取属性
        tvg_id = self._extract_attr(line, 'tvg-id')
        tvg_name = self._extract_attr(line, 'tvg-name')
        tvg_logo = self._extract_attr(line, 'tvg-logo')
        group_title = self._extract_attr(line, 'group-title')
        
        # 提取频道名称（在最后一个逗号后面）
        name = ''
        parts = line.split(',')
        if len(parts) > 1:
            name = parts[-1].strip()
        else:
            # 如果没有逗号，尝试从tvg-name获取
            name = tvg_name or tvg_id or '未知频道'
        
        return {
            'name': name,
            'tvg_id': tvg_id or name,
            'tvg_name': tvg_name or name,
            'tvg_logo': tvg_logo,
            'group': group_title or '默认',
            'url': ''
        }
    
    def _extract_attr(self, line: str, attr: str) -> str:
        """从EXTINF行提取指定属性"""
        pattern = rf'{attr}="([^"]*)"'
        match = re.search(pattern, line)
        if match:
            return match.group(1)
        
        # 尝试无引号格式
        pattern = rf'{attr}=([^\s,]+)'
        match = re.search(pattern, line)
        if match:
            return match.group(1)
        
        return ''
    
    def _is_valid_url(self, text: str) -> bool:
        """检查是否为有效URL"""
        try:
            result = urlparse(text)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _extract_name_from_url(self, url: str) -> str:
        """从URL提取文件名作为频道名"""
        try:
            path = urlparse(url).path
            name = path.split('/')[-1]
            if name:
                # 去除扩展名
                name = name.rsplit('.', 1)[0]
                return name.replace('_', ' ').replace('-', ' ')
        except:
            pass
        return '未知频道'
