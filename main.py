import os
import json
import requests
from io import BytesIO
from urllib.parse import urlparse
from base64 import b64decode
from flask import Flask, request, redirect, Response, render_template, send_from_directory

from proxy import Proxy
from youtube import YouTuBe


app = Flask(__name__)
class Spider():
    def get_playurl(self, rid, platform):
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"}
        if platform == 'youtube':
            playurl = YouTuBe().get_real_url(rid)
        elif platform == 'link':
            playurl = rid
        else:
            playurl = ''
        return playurl, header


@app.route('/')
def web():
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'templates'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/live')
def live():
    rid = request.args.get('rid')
    platform = request.args.get('platform')
    if rid is None or platform is None:
        return redirect('http://0.0.0.0/')

    result = urlparse(request.url)
    baseurl = '{}://{}'.format(result.scheme, result.netloc)
    playurl, header = Spider().get_playurl(rid, platform)
    if playurl == '':
        return redirect('http://0.0.0.0/')
    playcxt, is_m3u8 = Proxy().proxy_m3u8(playurl, baseurl, header)
    if is_m3u8 == 'True':
        return Response(BytesIO(playcxt.encode("utf-8")), mimetype="audio/x-mpegurl", headers={"Content-Disposition": "attachment; filename=proxied.m3u8"})
    elif is_m3u8 == 'False':
        return redirect(playcxt)
    else:
        return redirect('http://0.0.0.0/')


@app.route('/proxy')
def proxy():
    url = request.args.get('ts_url')
    header = request.args.get('headers')
    cxt_headers = dict(request.headers)
    if url is None or header is None:
        return redirect('http://0.0.0.0/')
    else:
        url = b64decode(url).decode("utf-8")
        header = b64decode(header).decode("utf-8")
        header = json.loads(header)
    try:
        for key in cxt_headers:
            if key.lower() in [
                'user-agent',
                'host',
            ]:
                continue
            header[key] = cxt_headers[key]
        if 'Connection' not in header:
            header['Connection'] = 'keep-alive'
        r = requests.get(url=url, headers=header, timeout=30, stream=True, verify=False)
        for key in r.headers:
            if key.lower() in [
                'connection',
                'transfer-encoding',
            ]:
                continue
            cxt_headers[key] = r.headers[key]
        if 'Range' in cxt_headers:
            status_code = 206
        else:
            status_code = 200
        return Response(download_file(r), status_code, cxt_headers)
    except:
        return redirect('http://0.0.0.0/')


def download_file(streamable):
    with streamable as stream:
        stream.raise_for_status()
        try:
            for chunk in stream.iter_content(chunk_size=40960):
                if chunk is None:
                    stream.close()
                    return
                yield chunk
        except:
            return


if __name__ == '__main__':
    app.run(host="0.0.0.0", threaded=True, port=8051)
