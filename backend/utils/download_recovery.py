"""Bounded media retries shared by legacy imports and Studio."""
from urllib.parse import urlparse
import yt_dlp


def download_with_recovery(url: str, options: dict):
    opts = {**options, 'socket_timeout': 30, 'retries': 2,
            'fragment_retries': 2, 'extractor_retries': 2,
            'concurrent_fragment_downloads': 1, 'skip_unavailable_fragments': False,
            'continuedl': True}
    youtube = urlparse(url).hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}
    retried_subtitles = retried_format = False
    while True:
        try:
            with yt_dlp.YoutubeDL(opts) as downloader:
                result = downloader.download([url])
            if result:
                raise RuntimeError('视频下载未完成，请检查网络后重试；已下载的分片将用于续传。')
            return result
        except yt_dlp.utils.DownloadError as error:
            text = str(error).lower()
            if not retried_subtitles and ('subtitle' in text or 'subtitles' in text) and (opts.get('writesubtitles') or opts.get('writeautomaticsub')):
                retried_subtitles = True
                opts.update(writesubtitles=False, writeautomaticsub=False)
                continue
            if youtube and not retried_format and any(code in text for code in ('http error 403', 'http error 500', 'requested format is not available')):
                retried_format = True
                opts['format'] = 'bestvideo[height<=1080][protocol*=m3u8]+bestaudio[protocol*=m3u8]/best[height<=1080][protocol*=m3u8]/best[ext=mp4]/best'
                continue
            raise
