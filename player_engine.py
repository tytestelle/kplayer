from ffpyplayer.player import MediaPlayer
import threading
import time

class PlayerEngine:
    def __init__(self):
        self.player = None
        self.is_playing = False
        self.is_paused = False
        self.current_url = ''
        self._callbacks = {}
        self._position = 0
        self._duration = 0
        self._thread = None
        self._stop_flag = False
        self._retry_count = 0
        self.max_retries = 3
        self.decoder = 'auto'  # 'auto', 'hardware', 'software'
        self.aspect_ratio = '16:9'  # 'original', '16:9', '4:3', 'fill'
        self._reconnect_enabled = True
    
    def play(self, url: str, headers: dict=None, user_agent: str=None, start_time: float=0):
        """播放URL，支持回看（start_time为秒）"""
        self.stop()
        self.current_url = url
        self._stop_flag = False
        self._retry_count = 0
        
        opts = {
            'fflags': 'nobuffer',
            'flags': 'low_delay',
            'framedrop': 1,
            'an': 0, 'vn': 0, 'sn': 0
        }
        # 解码器选择
        if self.decoder == 'hardware':
            opts['hwaccel'] = 'auto'
        elif self.decoder == 'software':
            opts['hwaccel'] = 'none'
        # 自定义headers
        if headers:
            opts['headers'] = ' '.join([f'{k}:{v}' for k,v in headers.items()])
        if user_agent:
            opts['user_agent'] = user_agent
        # 回看：seek到指定时间
        if start_time > 0:
            opts['seek'] = start_time
        
        self.player = MediaPlayer(url, ff_opts=opts)
        self.is_playing = True
        self.is_paused = False
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()
        self._trigger('on_play', url)
    
    def _play_loop(self):
        while self.is_playing and not self._stop_flag:
            if self.is_paused:
                time.sleep(0.1)
                continue
            frame, val = self.player.get_frame()
            if frame is None:
                if val == 'eof':
                    self._trigger('on_eos')
                elif val == 'error':
                    # 断线重连
                    if self._reconnect_enabled and self._retry_count < self.max_retries:
                        self._retry_count += 1
                        time.sleep(3)
                        self.play(self.current_url)  # 重连
                        return
                    else:
                        self._trigger('on_error', '播放失败')
                break
            self._position = self.player.get_pts()
            self._duration = self.player.get_duration()
            self._trigger('on_frame', frame)
            time.sleep(0.01)
    
    def set_aspect_ratio(self, ratio: str):
        self.aspect_ratio = ratio
        # 通过回调通知UI调整显示比例
    
    def seek_to(self, seconds: float):
        if self.player:
            self.player.seek(seconds, relative=False)
    
    # 其他方法（pause, resume, stop, set_volume, etc.）省略
