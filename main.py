from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty
from kivy.network.urlrequest import UrlRequest
import json
import threading
from channel_manager import ChannelManager
from epg_manager import EpgManager
from player_engine import PlayerEngine

class PlayerScreen(BoxLayout):
    current_channel_name = StringProperty('')
    epg_text = StringProperty('')
    playing = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.channel_mgr = ChannelManager()
        self.epg_mgr = EpgManager()
        self.player = PlayerEngine()
        self.player.set_callback('on_play', self.on_play)
        self.player.set_callback('on_eos', self.on_eos)
        self.player.set_callback('on_error', self.on_error)
        self.player.set_callback('on_frame', self.on_frame)
        
        # 加载配置
        self.load_config()
        # 加载频道列表
        self.load_playlist()
        # 启动EPG更新
        self.update_epg()
        Clock.schedule_interval(self.update_clock, 1)
        Clock.schedule_interval(lambda dt: self.epg_mgr.check_and_update(self.config.get('epg_sources', [])), 21600)
    
    def load_config(self):
        with open('config.json', 'r') as f:
            self.config = json.load(f)
    
    def load_playlist(self):
        url = self.config.get('playlist_url')
        if url:
            req = UrlRequest(url, on_success=self.on_playlist_loaded)
    
    def on_playlist_loaded(self, req, result):
        # 根据格式解析
        content = result.decode('utf-8')
        if 'EXTM3U' in content:
            self.channel_mgr.load_from_m3u(content)
        elif content.startswith('['):
            self.channel_mgr.load_from_json(json.loads(content))
        else:
            self.channel_mgr.load_from_txt(content)
        self.update_channel_list()
        if self.channel_mgr.channels:
            self.play_channel(0)
    
    def play_channel(self, index):
        ch = self.channel_mgr.channels[index]
        self.current_channel_name = ch.name
        self.player.play(ch.url, ch.headers, ch.user_agent)
        self.playing = True
        # 更新EPG信息
        self.update_epg_info(ch.epg_channel_id)
    
    def update_epg_info(self, channel_id):
        prog = self.epg_mgr.get_current_program(channel_id)
        if prog:
            start = datetime.fromtimestamp(prog.start_ts).strftime('%H:%M')
            end = datetime.fromtimestamp(prog.end_ts).strftime('%H:%M')
            self.epg_text = f'{start}-{end} {prog.title}'
        else:
            self.epg_text = '无节目信息'
    
    def toggle_play(self):
        self.player.toggle_pause()
        self.playing = not self.player.is_paused
    
    def prev(self):
        idx = self.channel_mgr.current_index - 1
        if idx < 0: idx = len(self.channel_mgr.channels) - 1
        self.play_channel(idx)
    
    def next(self):
        idx = (self.channel_mgr.current_index + 1) % len(self.channel_mgr.channels)
        self.play_channel(idx)
    
    def set_ratio(self, ratio_text):
        mapping = {'原始':'original', '16:9':'16:9', '4:3':'4:3', '填充':'fill'}
        self.player.set_aspect_ratio(mapping[ratio_text])
    
    def on_play(self, url):
        self.playing = True
    def on_eos(self):
        self.next()
    def on_error(self, msg):
        self.next()
    def on_frame(self, frame):
        # 更新视频显示（由VideoWidget处理）
        pass
    def update_clock(self, dt):
        self.ids.clock.text = datetime.now().strftime('%H:%M')
