"""
播放引擎 - 基于ffpyplayer (FFmpeg)
支持硬件加速、多音轨、快速定位
"""
from ffpyplayer.player import MediaPlayer
from ffpyplayer.tools import set_log_callback
import threading
import time


class PlayerEngine:
    """播放引擎封装"""
    
    def __init__(self):
        self.player = None
        self.is_playing = False
        self.is_paused = False
        self.current_url = ''
        self._callbacks = {}
        self._position = 0
        self._duration = 0
        self._play_thread = None
        self._stop_flag = False
        
        # 设置FFmpeg日志
        set_log_callback(self._ffmpeg_log)
    
    def play(self, url: str, opts: dict = None):
        """播放URL"""
        self.stop()
        
        self.current_url = url
        self._stop_flag = False
        
        # 播放选项
        default_opts = {
            'fflags': 'nobuffer',
            'flags': 'low_delay',
            'framedrop': 1,
            'an': 0,  # 启用音频
            'vn': 0,  # 启用视频
            'sn': 0,  # 禁用字幕
        }
        if opts:
            default_opts.update(opts)
        
        # 创建播放器
        self.player = MediaPlayer(url, ff_opts=default_opts)
        
        # 启动播放线程
        self.is_playing = True
        self.is_paused = False
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()
        
        self._trigger_callback('on_play', url)
    
    def _play_loop(self):
        """播放循环"""
        while self.is_playing and not self._stop_flag:
            if self.is_paused:
                time.sleep(0.1)
                continue
            
            # 获取帧
            frame, val = self.player.get_frame()
            
            if frame is None:
                # 播放结束
                if val == 'eof':
                    self._trigger_callback('on_eos')
                break
            
            # 更新播放位置
            self._position = self.player.get_pts()
            self._duration = self.player.get_duration()
            
            # 显示帧（由UI层处理）
            self._trigger_callback('on_frame', frame)
            
            time.sleep(0.01)
    
    def pause(self):
        """暂停"""
        if self.player and self.is_playing:
            self.is_paused = True
            self.player.toggle_pause()
            self._trigger_callback('on_pause')
    
    def resume(self):
        """恢复"""
        if self.player and self.is_playing and self.is_paused:
            self.is_paused = False
            self.player.toggle_pause()
            self._trigger_callback('on_resume')
    
    def toggle_pause(self):
        """切换暂停状态"""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
    
    def stop(self):
        """停止播放"""
        self.is_playing = False
        self._stop_flag = True
        if self.player:
            self.player.close_player()
            self.player = None
        self.current_url = ''
        self._trigger_callback('on_stop')
    
    def seek(self, position: float):
        """跳转到指定位置（秒）"""
        if self.player:
            self.player.seek(position, relative=False)
            self._trigger_callback('on_seek', position)
    
    def get_position(self) -> float:
        """获取当前播放位置"""
        return self._position
    
    def get_duration(self) -> float:
        """获取总时长"""
        return self._duration
    
    def set_volume(self, volume: float):
        """设置音量 0.0-1.0"""
        if self.player:
            self.player.set_volume(volume)
    
    def set_callback(self, event: str, callback):
        """设置事件回调"""
        self._callbacks[event] = callback
    
    def _trigger_callback(self, event: str, *args):
        """触发回调"""
        if event in self._callbacks:
            callback = self._callbacks[event]
            if callable(callback):
                callback(*args)
    
    def _ffmpeg_log(self, level, msg):
        """FFmpeg日志回调"""
        # 可选的日志处理
        pass
