"""
KU9-like 直播播放器
自主可控 | 支持多源EPG | 双缓冲更新 | 跨平台
"""
import json
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.core.window import Window

from m3u_parser import M3UParser
from epg_manager import EPGManager
from player_engine import PlayerEngine


class PlayerScreen(BoxLayout):
    """主播放界面"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = None
        self.channels = []
        self.current_channel_index = -1
        self.epg_manager = EPGManager()
        self.m3u_parser = M3UParser()
        
        # 加载配置
        self.load_config()
        
        # 初始化播放引擎
        self.init_player()
        
        # 加载直播源
        self.load_playlist()
        
        # 定时更新EPG（每6小时检查一次）
        Clock.schedule_interval(self.check_epg_update, 21600)
        
        # 启动后立即检查EPG
        Clock.schedule_once(lambda dt: self.check_epg_update(), 2)
    
    def load_config(self):
        """加载配置文件"""
        config_path = 'config.json'
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            # 默认配置
            self.config = {
                'playlist_url': '',  # 用户自行填入M3U地址
                'epg_sources': [],   # EPG数据源列表
                'theme': {
                    'primary_color': '#2196F3',
                    'background_color': '#1a1a2e'
                },
                'playback': {
                    'remember_position': True,
                    'buffer_size': 2048
                }
            }
            self.save_config()
    
    def save_config(self):
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def init_player(self):
        """初始化播放器"""
        self.player = PlayerEngine()
        self.player.set_callback('on_eos', self.on_playback_end)
        self.player.set_callback('on_error', self.on_playback_error)
    
    def load_playlist(self):
        """加载M3U播放列表"""
        playlist_url = self.config.get('playlist_url', '')
        if not playlist_url:
            Logger.warning('未配置直播源URL，请在config.json中设置playlist_url')
            self.show_message('请配置直播源')
            return
        
        try:
            self.channels = self.m3u_parser.parse_url(playlist_url)
            Logger.info(f'成功加载 {len(self.channels)} 个频道')
            
            # 更新频道列表UI
            self.update_channel_list()
            
            # 自动播放第一个频道
            if self.channels:
                self.play_channel(0)
        except Exception as e:
            Logger.error(f'加载播放列表失败: {e}')
            self.show_message(f'加载失败: {e}')
    
    def play_channel(self, index):
        """播放指定频道"""
        if index < 0 or index >= len(self.channels):
            return
        
        self.current_channel_index = index
        channel = self.channels[index]
        
        # 获取当前节目信息
        epg_info = self.epg_manager.get_current_program(
            channel.get('tvg_id', channel.get('name', '')),
            self.player.get_current_time() if self.player else 0
        )
        
        # 显示频道信息
        self.update_info(channel, epg_info)
        
        # 播放流
        self.player.play(channel['url'])
    
    def check_epg_update(self, dt=None):
        """检查并更新EPG（双缓冲，保留旧数据）"""
        epg_sources = self.config.get('epg_sources', [])
        if not epg_sources:
            return
        
        Logger.info('开始检查EPG更新...')
        self.epg_manager.check_and_update(epg_sources, callback=self.on_epg_updated)
    
    def on_epg_updated(self, success, count):
        """EPG更新回调"""
        if success:
            Logger.info(f'EPG更新成功，节目数: {count}')
        else:
            Logger.warning('EPG更新失败，保留旧数据')
    
    def on_playback_end(self):
        """播放结束自动播放下一个"""
        if self.current_channel_index >= 0:
            next_idx = (self.current_channel_index + 1) % len(self.channels)
            self.play_channel(next_idx)
    
    def on_playback_error(self, error_msg):
        """播放错误处理"""
        Logger.error(f'播放错误: {error_msg}')
        # 尝试下一个频道
        if self.current_channel_index >= 0:
            next_idx = (self.current_channel_index + 1) % len(self.channels)
            self.play_channel(next_idx)
    
    def update_channel_list(self):
        """更新频道列表UI"""
        # 在KV中实现
        pass
    
    def update_info(self, channel, epg):
        """更新当前播放信息"""
        # 在KV中实现
        pass
    
    def show_message(self, msg):
        """显示消息"""
        # 在KV中实现
        pass
    
    def on_stop(self):
        """应用退出时释放资源"""
        if self.player:
            self.player.stop()


class KU9PlayerApp(App):
    """应用主类"""
    
    def build(self):
        Window.size = (800, 480)  # 适合电视盒子的分辨率
        return PlayerScreen()
    
    def on_stop(self):
        self.root.on_stop()


if __name__ == '__main__':
    KU9PlayerApp().run()
